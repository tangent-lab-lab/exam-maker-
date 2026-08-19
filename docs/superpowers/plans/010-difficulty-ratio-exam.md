# Plan 010: 难度配比出卷 — 按比例从题库抽题

> **依赖**: Plan 004（Exam / Question 模型）、Plan 005（仪表盘入口）、Plan 006（知识点），题库中已有题目
> **预估改动**: ~28 行（修改 app.py + 新建模板）

## 对应 Spec 章节

四-2c. 按难度配比出卷 / 六、路由设计 / 七、teacher/create_exam_ratio.html

## 需要创建的文件

1. `exam_maker/templates/teacher/create_exam_ratio.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加难度配比出卷 GET + POST 路由

## 改动步骤

### Step 1: 在 `app.py` 路由区域添加难度配比出卷路由

```python
# ========== 难度配比出卷 ==========

@app.route("/teacher/create_exam/ratio", methods=["GET", "POST"])
@login_required
def create_exam_ratio():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))

    kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()

    if request.method == "GET":
        # 预检查题库是否有题目
        available = Question.query.filter_by(teacher_id=current_user.id).count()
        return render_template("teacher/create_exam_ratio.html", kps=kps, available=available)

    # POST: 按比例抽题
    title = request.form.get("title", "").strip()
    total = int(request.form.get("total", 10))
    qtypes = request.form.getlist("qtypes")  # 题型筛选
    ratio_easy = int(request.form.get("ratio_easy", 3))
    ratio_medium = int(request.form.get("ratio_medium", 5))
    ratio_hard = int(request.form.get("ratio_hard", 2))
    kp_filter = request.form.get("kp_filter", type=int)  # 可选知识点筛选

    # 计算各难度所需题数
    ratio_sum = ratio_easy + ratio_medium + ratio_hard
    need_easy = round(total * ratio_easy / ratio_sum)
    need_medium = round(total * ratio_medium / ratio_sum)
    need_hard = total - need_easy - need_medium  # 确保总数正确

    # 构建基础查询
    def build_query(diff):
        q = Question.query.filter_by(teacher_id=current_user.id, difficulty=diff)
        if qtypes:
            q = q.filter(Question.type.in_(qtypes))
        if kp_filter:
            q = q.join(question_knowledge_points).filter(
                question_knowledge_points.c.knowledge_point_id == kp_filter
            )
        return q

    # 检查各难度题目是否充足
    count_easy = build_query(1).count() if need_easy > 0 else need_easy
    count_medium = build_query(3).count() if need_medium > 0 else need_medium
    count_hard = build_query(5).count() if need_hard > 0 else need_hard

    errors = []
    if count_easy < need_easy:
        errors.append(f"简单题(难度1-2)不足：需要 {need_easy} 道，当前仅 {count_easy} 道")
    if count_medium < need_medium:
        errors.append(f"中等题(难度3)不足：需要 {need_medium} 道，当前仅 {count_medium} 道")
    if count_hard < need_hard:
        errors.append(f"困难题(难度4-5)不足：需要 {need_hard} 道，当前仅 {count_hard} 道")

    if errors:
        available = Question.query.filter_by(teacher_id=current_user.id).count()
        return render_template("teacher/create_exam_ratio.html", kps=kps, available=available,
                               error="; ".join(errors))

    # 随机抽取
    import random
    selected = []
    for diff, need in [(1, need_easy), (3, need_medium), (5, need_hard)]:
        if need <= 0:
            continue
        # 从该难度范围内随机选取
        qs = build_query(diff).all()
        # 难度映射：difficulty=1 取难度1-2, difficulty=3 取难度3, difficulty=5 取难度4-5
        if diff == 1:
            qs = [q for q in Question.query.filter_by(teacher_id=current_user.id).all()
                  if q.difficulty in (1, 2)]
        elif diff == 5:
            qs = [q for q in Question.query.filter_by(teacher_id=current_user.id).all()
                  if q.difficulty in (4, 5)]
        # 应用题型和知识点筛选
        if qtypes:
            qs = [q for q in qs if q.type in qtypes]
        if kp_filter:
            qs = [q for q in qs if any(
                kp_id == kp_filter for kp_id in [
                    r[0] for r in db.session.execute(
                        db.select(question_knowledge_points.c.knowledge_point_id).where(
                            question_knowledge_points.c.question_id == q.id
                        )
                    ).fetchall()
                ]
            )]

        random.shuffle(qs)
        selected.extend(qs[:need])

    if len(selected) < total:
        available = Question.query.filter_by(teacher_id=current_user.id).count()
        return render_template("teacher/create_exam_ratio.html", kps=kps, available=available,
                               error=f"符合条件的题目不足：需要 {total} 道，仅匹配到 {len(selected)} 道")

    # 组装为 Exam.questions_json 格式
    questions_json = []
    for q in selected[:total]:
        questions_json.append({
            "type": q.type,
            "question": q.question_text,
            "options": json.loads(q.options_json),
            "answer": q.answer,
            "difficulty": q.difficulty,
        })

    # 创建试卷
    exam = Exam(title=title, teacher_id=current_user.id,
                creation_mode="difficulty_ratio",
                questions_json=json.dumps(questions_json, ensure_ascii=False),
                status="published")
    db.session.add(exam); db.session.commit()
    return redirect(url_for("teacher_dashboard"))
```

### Step 2: 创建 `templates/teacher/create_exam_ratio.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>⚖️ 难度配比出卷</h2>
<a href="{{ url_for('create_exam_page') }}" class="btn btn-sm btn-outline-secondary mb-3">← 返回选择</a>

{% if available == 0 %}
<div class="alert alert-warning">题库中还没有题目。请先通过 <a href="{{ url_for('create_exam_ai') }}">AI 出卷</a>（勾选"存入题库"）或 <a href="{{ url_for('create_exam_upload') }}">手动上传</a> 来添加题目。</div>
{% endif %}

{% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}

<div class="card shadow p-3">
<form method="post">
  <div class="mb-3"><label class="form-label">试卷标题</label><input class="form-control" name="title" required></div>

  <div class="mb-3"><label class="form-label">总题数</label>
    <select class="form-select" name="total">
      <option value="5">5 题</option><option value="10" selected>10 题</option>
      <option value="15">15 题</option><option value="20">20 题</option>
      <option value="30">30 题</option>
    </select>
  </div>

  <div class="mb-3"><label class="form-label">题型筛选</label>
    <div>
      <label class="me-3"><input type="checkbox" name="qtypes" value="single" checked> 单选</label>
      <label class="me-3"><input type="checkbox" name="qtypes" value="multiple" checked> 多选</label>
      <label class="me-3"><input type="checkbox" name="qtypes" value="fill"> 填空</label>
    </div>
    <small class="text-muted">只勾选需要的题型，题库中该题型的题目才能被抽取</small>
  </div>

  <div class="mb-3"><label class="form-label">难度比例 — 简单 : 中等 : 困难</label>
    <div class="row g-2">
      <div class="col-4"><input class="form-control" type="number" name="ratio_easy" value="3" min="0" max="10">
        <small class="text-muted">简单（难度 1-2）</small></div>
      <div class="col-4"><input class="form-control" type="number" name="ratio_medium" value="5" min="0" max="10">
        <small class="text-muted">中等（难度 3）</small></div>
      <div class="col-4"><input class="form-control" type="number" name="ratio_hard" value="2" min="0" max="10">
        <small class="text-muted">困难（难度 4-5）</small></div>
    </div>
    <small class="text-muted">例如 3:5:2 表示简单题占 30%、中等题占 50%、困难题占 20%</small>
  </div>

  {% if kps %}
  <div class="mb-3"><label class="form-label">知识点筛选（可选）</label>
    <select class="form-select" name="kp_filter">
      <option value="">全部知识点</option>
      {% for kp in kps %}
      <option value="{{ kp.id }}">{{ kp.name }}</option>
      {% endfor %}
    </select>
    <small class="text-muted">仅从关联了该知识点的题目中抽取</small>
  </div>
  {% endif %}

  <button type="submit" class="btn btn-info w-100" {% if available == 0 %}disabled{% endif %}>按比例生成试卷</button>
</form></div>
{% endblock %}
```

## 验收标准
- 教师进入难度配比出卷页 → 看到表单（标题、总题数、题型、难度比例、知识点筛选）
- 题库中无题目时 → 页面提示先补充题库，按钮禁用
- 输入标题 + 总题数 20 + 比例 3:5:2 → 点生成 → 系统从题库中按比例抽取（简单 6、中等 10、困难 4）→ 试卷创建成功，`creation_mode = difficulty_ratio`
- 某难度题目不足 → 返回表单页显示具体错误（"困难题不足，当前仅 2 道"）
- 试卷题目为随机抽取，每次生成的试卷题目不重复
