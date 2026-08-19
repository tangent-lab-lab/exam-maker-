# Plan 008: 手动上传出卷 — 文件解析 + 预览确认 + 入库

> **依赖**: Plan 004（Exam / Question / KnowledgePoint 模型）、Plan 005（仪表盘入口）、Plan 007（call_llm 函数已存在）
> **预估改动**: ~30 行（修改 app.py + 新建 2 个模板）

## 对应 Spec 章节

四-2b. 手动上传试卷 / 五-5b. 文件解析提示词 / 六、路由设计 / 七、页面速写

## 需要创建的文件

1. `exam_maker/templates/teacher/create_exam_upload.html`（上传页）
2. `exam_maker/templates/teacher/create_exam_upload_preview.html`（预览确认页）

## 需要修改的文件

1. `exam_maker/app.py` — 添加文件解析函数 + 上传/预览/确认/取消路由

## 改动步骤

### Step 1: 在 `app.py` 的 call_llm 函数之后，添加文件文本提取函数

```python
def extract_text(file):
    """根据文件扩展名提取文本内容"""
    filename = file.filename.lower()
    if filename.endswith(".txt"):
        return file.read().decode("utf-8")
    elif filename.endswith(".docx"):
        from docx import Document
        doc = Document(file)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    elif filename.endswith(".pdf"):
        from PyPDF2 import PdfReader
        reader = PdfReader(file)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        raise ValueError("不支持的文件格式，仅支持 .docx / .pdf / .txt")
```

### Step 2: 添加上传出卷路由

```python
# ========== 手动上传出卷 ==========

@app.route("/teacher/create_exam/upload", methods=["GET", "POST"])
@login_required
def create_exam_upload():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    if request.method == "GET":
        kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()
        return render_template("teacher/create_exam_upload.html", kps=kps)

    # POST: 上传文件 + LLM 解析
    title = request.form.get("title", "").strip()
    file = request.files.get("file")
    if not file or not title:
        kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()
        return render_template("teacher/create_exam_upload.html", kps=kps, error="请填写标题并选择文件")

    try:
        text = extract_text(file)
    except ValueError as e:
        kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()
        return render_template("teacher/create_exam_upload.html", kps=kps, error=str(e))

    prompt = (
        "你是一个试卷解析助手。以下是从上传文件中提取的文本内容，请将其中的题目结构化。\n"
        "每道题包含：type(题型:single/multiple/fill),question(题干),options(选项列表,非选择题为空数组[]),"
        "answer(正确答案),difficulty(难度1-5,根据题目复杂度自行判断)。\n"
        "只返回 JSON 数组，不要任何其他内容。\n\n文本内容：\n" + text[:6000]
    )

    try:
        raw = call_llm(prompt)
        questions = json.loads(raw.strip().removeprefix("```json").removesuffix("```"))
    except Exception as e:
        kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()
        return render_template("teacher/create_exam_upload.html", kps=kps,
                               error=f"AI 解析失败: {e}")

    # 存入 session 供预览，暂不入库
    from flask import session
    session["preview_title"] = title
    session["preview_questions"] = json.dumps(questions, ensure_ascii=False)
    session["preview_kp_ids"] = request.form.getlist("kp_ids")
    return redirect(url_for("create_exam_upload_preview"))
```

### Step 3: 添加预览确认 / 取消路由

```python
@app.route("/teacher/create_exam/upload/preview")
@login_required
def create_exam_upload_preview():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    title = session.get("preview_title", "")
    questions = json.loads(session.get("preview_questions", "[]"))
    if not questions:
        return redirect(url_for("create_exam_upload"))
    return render_template("teacher/create_exam_upload_preview.html", title=title, questions=questions)


@app.route("/teacher/create_exam/upload/confirm", methods=["POST"])
@login_required
def create_exam_upload_confirm():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    title = session.get("preview_title", "未命名试卷")
    questions_json = session.get("preview_questions", "[]")
    kp_ids_raw = session.get("preview_kp_ids", [])
    questions = json.loads(questions_json)

    # 逐题入库
    for q in questions:
        question = Question(
            teacher_id=current_user.id,
            type=q.get("type", "single"),
            question_text=q.get("question", ""),
            options_json=json.dumps(q.get("options", []), ensure_ascii=False),
            answer=str(q.get("answer", "")),
            difficulty=int(q.get("difficulty", 3)),
            source="manual_upload",
        )
        db.session.add(question)
        db.session.flush()  # 获取 question.id
        # 关联知识点
        for kp_id in kp_ids_raw:
            db.session.execute(
                question_knowledge_points.insert().values(
                    question_id=question.id, knowledge_point_id=int(kp_id)
                )
            )
    db.session.commit()

    # 创建试卷
    exam = Exam(title=title, teacher_id=current_user.id,
                creation_mode="manual_upload",
                questions_json=questions_json, status="published")
    db.session.add(exam); db.session.commit()

    # 清理 session
    session.pop("preview_title", None)
    session.pop("preview_questions", None)
    session.pop("preview_kp_ids", None)
    return redirect(url_for("teacher_dashboard"))


@app.route("/teacher/create_exam/upload/cancel", methods=["POST"])
@login_required
def create_exam_upload_cancel():
    session.pop("preview_title", None)
    session.pop("preview_questions", None)
    session.pop("preview_kp_ids", None)
    return redirect(url_for("create_exam_upload"))
```

### Step 4: 创建 `templates/teacher/create_exam_upload.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>📤 手动上传出卷</h2>
<a href="{{ url_for('create_exam_page') }}" class="btn btn-sm btn-outline-secondary mb-3">← 返回选择</a>
{% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}
<div class="card shadow p-3">
<form method="post" enctype="multipart/form-data">
  <div class="mb-3"><label class="form-label">试卷标题</label><input class="form-control" name="title" required></div>
  <div class="mb-3"><label class="form-label">上传试卷文件</label>
    <input class="form-control" type="file" name="file" accept=".docx,.pdf,.txt" required>
    <small class="text-muted">支持 .docx / .pdf / .txt 格式</small>
  </div>
  {% if kps %}
  <div class="mb-3"><label class="form-label">关联知识点（可选）</label>
    <div>
      {% for kp in kps %}
      <label class="me-3"><input type="checkbox" name="kp_ids" value="{{ kp.id }}"> {{ kp.name }}</label>
      {% endfor %}
    </div>
  </div>
  {% endif %}
  <button type="submit" class="btn btn-success w-100">上传并解析</button>
</form></div>
{% endblock %}
```

### Step 5: 创建 `templates/teacher/create_exam_upload_preview.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>📤 解析预览 — {{ title }}</h2>
<div class="alert alert-info">AI 解析出 <strong>{{ questions|length }}</strong> 道题目，请确认后保存。</div>

{% for q in questions %}
<div class="card mb-2">
  <div class="card-body">
    <p><strong>{{ loop.index }}. {{ q.question }}</strong>
      <span class="badge bg-secondary">{{ q.type }}</span>
      <span class="badge bg-info">难度 {{ q.difficulty }}</span></p>
    {% if q.options %}
    <ul>{% for opt in q.options %}<li>{{ opt }}</li>{% endfor %}</ul>
    {% endif %}
    <p class="text-success small">答案：{{ q.answer }}</p>
  </div>
</div>
{% endfor %}

<form method="post" class="d-flex gap-2">
  <button formaction="{{ url_for('create_exam_upload_confirm') }}" class="btn btn-success">✓ 确认保存</button>
  <button formaction="{{ url_for('create_exam_upload_cancel') }}" class="btn btn-outline-danger">✗ 取消</button>
</form>
{% endblock %}
```

## 验收标准
- 教师进入上传页 → 输入标题 + 选择 .docx/.pdf/.txt 文件 → 点"上传并解析"
- 等待 AI 解析 → 跳转到预览页，显示结构化题目列表（每道题展示类型、难度、选项、答案）
- 点"确认保存"→ 题目写入 `questions` 表 + 试卷创建（`creation_mode = manual_upload`）
- 点"取消"→ 题目不保存，返回上传页
- 若上传了关联的知识点，题目-知识点关联正确写入
