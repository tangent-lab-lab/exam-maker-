# Plan 011: 学生端 — 试卷列表 + 答题页

> **依赖**: Plan 003（auth 路由）、Plan 004（Exam 模型，题库中已存在 published 试卷）
> **预估改动**: ~22 行（修改 app.py + 新建 2 个模板）

## 对应 Spec 章节

四、功能清单（5. 学生答题）/ 六、路由设计 / 七、student/dashboard.html + student/take_exam.html

## 需要创建的文件

1. `exam_maker/templates/student/dashboard.html`
2. `exam_maker/templates/student/take_exam.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加学生仪表盘 + 答题页 GET 路由

## 改动步骤

### Step 1: 在 `app.py` 中添加学生端路由

```python
# ========== 学生仪表盘 ==========

@app.route("/student/dashboard")
@login_required
def student_dashboard():
    if current_user.role != "student":
        return redirect(url_for("teacher_dashboard"))
    exams = Exam.query.filter_by(status="published").order_by(Exam.created_at.desc()).all()
    return render_template("student/dashboard.html", exams=exams)


# ========== 学生答题 ==========

@app.route("/student/exam/<int:exam_id>")
@login_required
def take_exam(exam_id):
    if current_user.role != "student":
        return redirect(url_for("teacher_dashboard"))
    exam = db.session.get(Exam, exam_id)
    if not exam or exam.status != "published":
        return "试卷不存在", 404
    questions = json.loads(exam.questions_json)
    return render_template("student/take_exam.html", exam=exam, questions=questions)
```

### Step 2: 创建 `templates/student/dashboard.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>可答试卷</h2>
{% if exams %}
<table class="table table-bordered bg-white">
  <thead><tr><th>试卷名称</th><th>出卷教师</th><th>出卷方式</th><th>创建时间</th><th>操作</th></tr></thead>
  <tbody>{% for e in exams %}
    <tr><td>{{ e.title }}</td><td>{{ e.teacher.username }}</td>
      <td><span class="badge bg-secondary">{{ e.creation_mode }}</span></td>
      <td>{{ e.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
      <td><a href="{{ url_for('take_exam', exam_id=e.id) }}" class="btn btn-sm btn-primary">进入答题</a></td></tr>
  {% endfor %}</tbody>
</table>
{% else %}<p>暂无可用试卷。</p>{% endif %}
{% endblock %}
```

### Step 3: 创建 `templates/student/take_exam.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ exam.title }}</h2>
<form method="post" action="{{ url_for('submit_exam', exam_id=exam.id) }}">
  {% for q in questions %}
  <div class="card mb-3">
    <div class="card-body">
      <h6>{{ loop.index }}. {{ q.question }}
        <span class="badge bg-secondary">{{ q.type }}</span>
        {% if q.difficulty %}<span class="badge bg-info">难度 {{ q.difficulty }}</span>{% endif %}
      </h6>
      {% if q.type == 'single' and q.options %}
        {% for opt in q.options %}
        <div class="form-check"><input class="form-check-input" type="radio" name="q{{ loop.parent.index0 }}" value="{{ opt }}" required>
          <label class="form-check-label">{{ opt }}</label></div>
        {% endfor %}
      {% elif q.type == 'multiple' and q.options %}
        {% for opt in q.options %}
        <div class="form-check"><input class="form-check-input" type="checkbox" name="q{{ loop.parent.index0 }}" value="{{ opt }}">
          <label class="form-check-label">{{ opt }}</label></div>
        {% endfor %}
      {% else %}
        <input class="form-control" name="q{{ loop.index0 }}" placeholder="请输入答案" required>
      {% endif %}
    </div>
  </div>
  {% endfor %}
  <button type="submit" class="btn btn-success btn-lg w-100">交卷</button>
</form>
{% endblock %}
```

## 验收标准
- 学生登录后自动跳转到 `/student/dashboard`
- 列表中出现所有 `published` 试卷（不论 `creation_mode`），未发布的不显示
- 点"进入答题"→ 看到试题渲染（单选 radio、多选 checkbox、填空 input），三种出卷方式产生的试卷均正常显示
- 未填完提交时 HTML5 `required` 阻止
