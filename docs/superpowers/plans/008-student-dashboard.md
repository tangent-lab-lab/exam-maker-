# Plan 008: 学生仪表盘 — 可答试卷列表

> **依赖**: Plan 003（auth 路由）、Plan 004（Exam 模型）
> **预估改动**: ~15 行（修改 app.py + 新建模板）

## 对应 Spec 章节

四、功能清单（3. 学生答题 → 仪表盘列出 published 试卷）/ 六、路由设计（GET /student/dashboard）

## 需要创建的文件

1. `exam_maker/templates/student/dashboard.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加学生仪表盘路由

## 改动步骤

### Step 1: 在 `app.py` 中添加学生仪表盘路由

```python
@app.route("/student/dashboard")
@login_required
def student_dashboard():
    if current_user.role != "student":
        return redirect(url_for("teacher_dashboard"))
    exams = Exam.query.filter_by(status="published").order_by(Exam.created_at.desc()).all()
    return render_template("student/dashboard.html", exams=exams)
```

### Step 2: 创建 `templates/student/dashboard.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>可答试卷</h2>
{% if exams %}
<table class="table table-bordered bg-white">
  <thead><tr><th>试卷名称</th><th>出卷教师</th><th>创建时间</th><th>操作</th></tr></thead>
  <tbody>{% for e in exams %}
    <tr><td>{{ e.title }}</td><td>{{ e.teacher.username }}</td>
      <td>{{ e.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
      <td><a href="{{ url_for('take_exam', exam_id=e.id) }}" class="btn btn-sm btn-primary">进入答题</a></td></tr>
  {% endfor %}</tbody>
</table>
{% else %}<p>暂无可用试卷。</p>{% endif %}
{% endblock %}
```

## 验收标准
- 教师创建并发布试卷后，学生登录自动跳转到 `/student/dashboard`
- 列表中出现该试卷，显示"进入答题"按钮
- 未发布（status=draft）的试卷不出现在列表中
