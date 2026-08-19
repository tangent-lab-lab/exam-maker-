# Plan 009: 题库管理 — 浏览 / 筛选 / 编辑 / 删除

> **依赖**: Plan 004（Question / KnowledgePoint 模型）、Plan 005（仪表盘入口）、Plan 006（知识点已可管理）
> **预估改动**: ~30 行（修改 app.py + 新建模板）

## 对应 Spec 章节

四、功能清单（4. 题库管理）/ 六、路由设计 / 七、teacher/question_bank.html

## 需要创建的文件

1. `exam_maker/templates/teacher/question_bank.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加题库列表 + 编辑 + 删除路由

## 改动步骤

### Step 1: 在 `app.py` 路由区域添加题库管理路由

```python
# ========== 题库管理 ==========

@app.route("/teacher/question_bank")
@login_required
def question_bank():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))

    # 筛选参数
    kp_filter = request.args.get("kp", type=int)
    difficulty_filter = request.args.get("difficulty", type=int)
    type_filter = request.args.get("type", "")

    query = Question.query.filter_by(teacher_id=current_user.id)
    if difficulty_filter:
        query = query.filter_by(difficulty=difficulty_filter)
    if type_filter:
        query = query.filter_by(type=type_filter)
    if kp_filter:
        query = query.join(question_knowledge_points).filter(
            question_knowledge_points.c.knowledge_point_id == kp_filter
        )

    questions = query.order_by(Question.created_at.desc()).all()
    kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()

    # 为每道题预加载其知识点
    q_with_kps = []
    for q in questions:
        kp_ids = [r[0] for r in db.session.execute(
            db.select(question_knowledge_points.c.knowledge_point_id).where(
                question_knowledge_points.c.question_id == q.id
            )
        ).fetchall()]
        q_kps = KnowledgePoint.query.filter(KnowledgePoint.id.in_(kp_ids)).all() if kp_ids else []
        q_with_kps.append((q, q_kps))

    return render_template("teacher/question_bank.html",
                           questions=q_with_kps, kps=kps,
                           kp_filter=kp_filter, difficulty_filter=difficulty_filter, type_filter=type_filter)


@app.route("/teacher/question/<int:q_id>/edit", methods=["POST"])
@login_required
def edit_question(q_id):
    q = Question.query.filter_by(id=q_id, teacher_id=current_user.id).first()
    if not q:
        return redirect(url_for("question_bank"))
    q.question_text = request.form.get("question_text", q.question_text)
    q.type = request.form.get("type", q.type)
    q.options_json = request.form.get("options_json", q.options_json)
    q.answer = request.form.get("answer", str(q.answer))
    q.difficulty = int(request.form.get("difficulty", q.difficulty))

    # 更新知识点关联
    kp_ids = request.form.getlist("kp_ids")
    db.session.execute(
        question_knowledge_points.delete().where(
            question_knowledge_points.c.question_id == q.id
        )
    )
    for kp_id in kp_ids:
        db.session.execute(
            question_knowledge_points.insert().values(
                question_id=q.id, knowledge_point_id=int(kp_id)
            )
        )
    db.session.commit()
    return redirect(url_for("question_bank"))


@app.route("/teacher/question/<int:q_id>/delete", methods=["POST"])
@login_required
def delete_question(q_id):
    q = Question.query.filter_by(id=q_id, teacher_id=current_user.id).first()
    if q:
        db.session.execute(
            question_knowledge_points.delete().where(
                question_knowledge_points.c.question_id == q.id
            )
        )
        db.session.delete(q)
        db.session.commit()
    return redirect(url_for("question_bank"))
```

### Step 2: 创建 `templates/teacher/question_bank.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>📦 题库管理</h2>
<a href="{{ url_for('teacher_dashboard') }}" class="btn btn-sm btn-outline-secondary mb-3">← 返回仪表盘</a>

<!-- 筛选栏 -->
<form class="row g-2 mb-3" method="get">
  <div class="col-md-3">
    <select class="form-select form-select-sm" name="kp">
      <option value="">全部知识点</option>
      {% for kp in kps %}
      <option value="{{ kp.id }}" {% if kp_filter == kp.id %}selected{% endif %}>{{ kp.name }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-md-2">
    <select class="form-select form-select-sm" name="difficulty">
      <option value="">全部难度</option>
      {% for d in range(1,6) %}
      <option value="{{ d }}" {% if difficulty_filter == d %}selected{% endif %}>难度 {{ d }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-md-2">
    <select class="form-select form-select-sm" name="type">
      <option value="">全部题型</option>
      <option value="single" {% if type_filter == 'single' %}selected{% endif %}>单选</option>
      <option value="multiple" {% if type_filter == 'multiple' %}selected{% endif %}>多选</option>
      <option value="fill" {% if type_filter == 'fill' %}selected{% endif %}>填空</option>
    </select>
  </div>
  <div class="col-md-2"><button type="submit" class="btn btn-sm btn-outline-primary w-100">筛选</button></div>
</form>

<!-- 题目列表 -->
{% if questions %}
{% for q, q_kps in questions %}
<div class="card mb-2">
  <div class="card-body">
    <div class="d-flex justify-content-between align-items-start">
      <div>
        <strong>{{ q.question_text | truncate(80) }}</strong>
        <div class="mt-1">
          <span class="badge bg-secondary">{{ q.type }}</span>
          <span class="badge bg-info">难度 {{ q.difficulty }}</span>
          <span class="badge bg-light text-dark">{{ q.source }}</span>
          {% for kp in q_kps %}<span class="badge bg-warning text-dark">{{ kp.name }}</span>{% endfor %}
        </div>
        <small class="text-muted">答案：{{ q.answer | truncate(60) }}</small>
      </div>
      <div class="btn-group btn-group-sm">
        <button class="btn btn-outline-warning" onclick="toggleEdit({{ q.id }})">编辑</button>
        <form method="post" action="{{ url_for('delete_question', q_id=q.id) }}" style="display:inline"
              onsubmit="return confirm('确定删除此题？')">
          <button class="btn btn-outline-danger">删除</button>
        </form>
      </div>
    </div>
    <!-- 编辑区（默认隐藏） -->
    <form method="post" action="{{ url_for('edit_question', q_id=q.id) }}" class="mt-2 d-none" id="edit-{{ q.id }}">
      <textarea class="form-control form-control-sm mb-1" name="question_text" rows="2">{{ q.question_text }}</textarea>
      <div class="row g-1 mb-1">
        <div class="col-3"><select class="form-select form-select-sm" name="type">
          <option value="single" {% if q.type=='single' %}selected{% endif %}>单选</option>
          <option value="multiple" {% if q.type=='multiple' %}selected{% endif %}>多选</option>
          <option value="fill" {% if q.type=='fill' %}selected{% endif %}>填空</option>
        </select></div>
        <div class="col-2"><select class="form-select form-select-sm" name="difficulty">
          {% for d in range(1,6) %}<option value="{{ d }}" {% if q.difficulty==d %}selected{% endif %}>{{ d }}</option>{% endfor %}
        </select></div>
        <div class="col-3"><input class="form-control form-control-sm" name="answer" value="{{ q.answer }}"></div>
        <div class="col-4"><input class="form-control form-control-sm" name="options_json" value="{{ q.options_json }}"></div>
      </div>
      <div class="mb-1">
        {% for kp in kps %}
        <label class="me-2 small"><input type="checkbox" name="kp_ids" value="{{ kp.id }}"
          {% if kp in q_kps %}checked{% endif %}> {{ kp.name }}</label>
        {% endfor %}
      </div>
      <button type="submit" class="btn btn-sm btn-success">保存</button>
      <button type="button" class="btn btn-sm btn-outline-secondary" onclick="toggleEdit({{ q.id }})">取消</button>
    </form>
  </div>
</div>
{% endfor %}
{% else %}<p>题库为空。请先通过 AI 出卷（勾选"存入题库"）或手动上传来添加题目。</p>{% endif %}

<script>
function toggleEdit(id) { document.getElementById('edit-' + id).classList.toggle('d-none'); }
</script>
{% endblock %}
```

## 验收标准
- 教师进入题库管理 → 看到题目列表（如果已有题目入库）
- 按知识点、难度、题型筛选 → 列表正确过滤
- 点"编辑"→ 展开编辑区 → 修改题干/答案/知识点关联 → 保存成功
- 点"删除"→ 确认后题目被删除，关联表同时清理
- 筛选项和编辑项仅显示本教师的私有数据
