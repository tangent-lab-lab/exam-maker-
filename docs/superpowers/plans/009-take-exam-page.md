# Plan 009: 答题页 — GET 路由 + 模板

> **依赖**: Plan 008（学生仪表盘可跳转至此）
> **预估改动**: ~22 行（修改 app.py + 新建模板）

## 对应 Spec 章节

四、功能清单（3. 学生答题）/ 六、路由设计（GET /student/exam/<id>）/ 七、student/take_exam.html

## 需要创建的文件

1. `exam_maker/templates/student/take_exam.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加答题页 GET 路由

## 改动步骤

### Step 1: 在 `app.py` 中添加答题页路由

```python
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

### Step 2: 创建 `templates/student/take_exam.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ exam.title }}</h2>
<form method="post" action="{{ url_for('submit_exam', exam_id=exam.id) }}">
  {% for q in questions %}
  <div class="card mb-3">
    <div class="card-body">
      <h6>{{ loop.index }}. {{ q.question }} <span class="badge bg-secondary">{{ q.type }}</span></h6>
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
- 学生点"进入答题" → 看到试卷标题 + 所有题目（单选 radio、多选 checkbox、填空 input 对应渲染）
- 每种题型的表单控件正确显示
- 未答题提交时 HTML5 `required` 属性阻止提交
