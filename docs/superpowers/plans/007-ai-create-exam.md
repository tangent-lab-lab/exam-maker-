# Plan 007: AI 出卷 — LLM 调用 + 表单 + 可选入库

> **依赖**: Plan 004（Exam 模型）、Plan 005（仪表盘入口）
> **预估改动**: ~30 行（修改 app.py + 新建 2 个模板）

## 对应 Spec 章节

四-2a. AI 出卷 / 五-5a. AI 出卷提示词 / 六、路由设计 / 七、页面速写

## 需要创建的文件

1. `exam_maker/templates/teacher/create_exam.html`（出卷方式选择页）
2. `exam_maker/templates/teacher/create_exam_ai.html`（AI 出卷表单）

## 需要修改的文件

1. `exam_maker/app.py` — 添加 AI 调用函数 + 出卷方式选择路由 + AI 出卷 GET/POST 路由

## 改动步骤

### Step 1: 在 `app.py` 的 `load_dotenv()` 之后，添加 AI 调用函数

```python
import httpx

def call_llm(prompt: str) -> str:
    resp = httpx.post(
        f"{os.getenv('LLM_BASE_URL')}/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('LLM_API_KEY')}"},
        json={"model": os.getenv("LLM_MODEL"), "messages": [{"role":"user","content":prompt}]},
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
```

### Step 2: 添加出卷方式选择路由

```python
# ========== 出卷方式选择 ==========

@app.route("/teacher/create_exam")
@login_required
def create_exam_page():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    return render_template("teacher/create_exam.html")
```

### Step 3: 添加 AI 出卷 GET + POST 路由

```python
# ========== AI 出卷 ==========

@app.route("/teacher/create_exam/ai", methods=["GET", "POST"])
@login_required
def create_exam_ai():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    if request.method == "GET":
        return render_template("teacher/create_exam_ai.html")

    title = request.form["title"]
    count = int(request.form["count"])
    difficulty = request.form["difficulty"]
    qtypes = request.form.getlist("qtypes")
    save_to_bank = request.form.get("save_to_bank") == "1"

    prompt = (
        f"你是一个出题助手。请生成{count}道题目，难度{difficulty}/5，题型包含{','.join(qtypes)}。"
        f"每题包含：type(题型:single/multiple/fill),question(题干),options(选项列表,非选择题为空数组[]),"
        f"answer(正确答案),difficulty(难度1-5)。只返回JSON数组，不要任何其他内容。"
    )

    try:
        raw = call_llm(prompt)
        questions = json.loads(raw.strip().removeprefix("```json").removesuffix("```"))
    except Exception as e:
        return render_template("teacher/create_exam_ai.html", error=f"AI 出卷失败: {e}")

    # 创建试卷
    exam = Exam(title=title, teacher_id=current_user.id,
                creation_mode="ai_generate",
                questions_json=json.dumps(questions, ensure_ascii=False),
                status="published")
    db.session.add(exam); db.session.commit()

    # 可选：存入题库
    if save_to_bank:
        for q in questions:
            question = Question(
                teacher_id=current_user.id,
                type=q.get("type", "single"),
                question_text=q.get("question", ""),
                options_json=json.dumps(q.get("options", []), ensure_ascii=False),
                answer=str(q.get("answer", "")),
                difficulty=int(q.get("difficulty", difficulty)),
                source="ai_generate",
            )
            db.session.add(question)
        db.session.commit()

    return redirect(url_for("teacher_dashboard"))
```

### Step 4: 创建 `templates/teacher/create_exam.html`（出卷方式选择页）

```html
{% extends "base.html" %}
{% block content %}
<h2>选择出卷方式</h2>
<div class="row mt-4">
  <div class="col-md-4">
    <div class="card text-center p-4 shadow">
      <h3>🤖</h3><h5>AI 出卷</h5>
      <p class="text-muted">告诉 AI 你的需求，秒出试卷</p>
      <a href="{{ url_for('create_exam_ai') }}" class="btn btn-primary">开始</a>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card text-center p-4 shadow">
      <h3>📤</h3><h5>手动上传</h5>
      <p class="text-muted">上传 Word/PDF/TXT，自动解析入库</p>
      <a href="{{ url_for('create_exam_upload') }}" class="btn btn-success">开始</a>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card text-center p-4 shadow">
      <h3>⚖️</h3><h5>难度配比</h5>
      <p class="text-muted">指定难度比例，从题库自动抽取</p>
      <a href="{{ url_for('create_exam_ratio') }}" class="btn btn-info">开始</a>
    </div>
  </div>
</div>
{% endblock %}
```

### Step 5: 创建 `templates/teacher/create_exam_ai.html`（AI 出卷表单）

```html
{% extends "base.html" %}
{% block content %}
<h2>🤖 AI 出卷</h2>
<a href="{{ url_for('create_exam_page') }}" class="btn btn-sm btn-outline-secondary mb-3">← 返回选择</a>
{% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}
<div class="card shadow p-3">
<form method="post">
  <div class="mb-3"><label class="form-label">试卷标题</label><input class="form-control" name="title" required></div>
  <div class="mb-3"><label class="form-label">题目数量</label>
    <select class="form-select" name="count">
      <option value="5">5 题</option><option value="10" selected>10 题</option><option value="15">15 题</option><option value="20">20 题</option>
    </select></div>
  <div class="mb-3"><label class="form-label">难度</label>
    <div>{% for i in range(1,6) %}
      <label class="me-3"><input type="radio" name="difficulty" value="{{ i }}" {% if i==3 %}checked{% endif %}> {{ i }}</label>
    {% endfor %}</div></div>
  <div class="mb-3"><label class="form-label">题型</label>
    <div>
      <label class="me-3"><input type="checkbox" name="qtypes" value="single" checked> 单选</label>
      <label class="me-3"><input type="checkbox" name="qtypes" value="multiple" checked> 多选</label>
      <label class="me-3"><input type="checkbox" name="qtypes" value="fill"> 填空</label>
    </div></div>
  <div class="mb-3 form-check">
    <input type="checkbox" class="form-check-input" name="save_to_bank" value="1" id="saveBank">
    <label class="form-check-label" for="saveBank">同时存入题库（供后续难度配比出卷复用）</label>
  </div>
  <button type="submit" class="btn btn-primary w-100">生成试卷</button>
</form></div>
{% endblock %}
```

## 验收标准
- 教师进入 `/teacher/create_exam` → 看到三种出卷方式卡片
- 点"AI 出卷"→ 填参数(数量=5, 难度=3, 题型=单选/多选) → 点生成 → 等待 5-15 秒 → 回到仪表盘看到新试卷，`creation_mode` 为 `ai_generate`
- 勾选"同时存入题库"→ 生成后 `questions` 表中有对应题目
- 不勾选 → 不写入题库
