# Plan 005: 教师仪表盘 — 试卷列表

> **依赖**: Plan 003（auth 路由）、Plan 004（Exam 模型）
> **预估改动**: ~15 行（修改 app.py + 新建模板）

## 对应 Spec 章节

四、功能清单（2. 教师 AI 出卷 → 仪表盘）/ 六、路由设计（GET /teacher/dashboard）

## 需要创建的文件

1. `exam_maker/templates/teacher/dashboard.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加教师仪表盘路由

## 改动步骤

### Step 1: 在 `app.py` auth 路由之后添加

```python
@app.route("/teacher/dashboard")
@login_required
def teacher_dashboard():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    exams = Exam.query.filter_by(teacher_id=current_user.id).order_by(Exam.created_at.desc()).all()
    return render_template("teacher/dashboard.html", exams=exams)
```

### Step 2: 创建 `templates/teacher/dashboard.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>教师仪表盘</h2>
<a href="{{ url_for('create_exam_page') }}" class="btn btn-primary mb-3">创建试卷</a>
{% if exams %}
<table class="table table-bordered bg-white">
  <thead><tr><th>试卷名称</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
  <tbody>{% for e in exams %}
    <tr><td>{{ e.title }}</td><td>{{ e.status }}</td><td>{{ e.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
      <td><a href="{{ url_for('exam_results', exam_id=e.id) }}" class="btn btn-sm btn-outline-info">查看成绩</a></td></tr>
  {% endfor %}</tbody>
</table>
{% else %}<p>还没有创建任何试卷。</p>{% endif %}
{% endblock %}
```

## 验收标准
- 教师登录后自动跳转到 `/teacher/dashboard`
- 页面显示"创建试卷"按钮 + 空试卷列表（因为还没创建试卷）
- 学生角色访问此页 → 自动重定向到学生仪表盘
