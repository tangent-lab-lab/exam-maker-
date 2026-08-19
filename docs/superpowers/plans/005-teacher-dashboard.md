# Plan 005: 教师仪表盘 — 试卷列表 + 出卷入口 + 题库入口

> **依赖**: Plan 003（auth 路由）、Plan 004（Exam / Question / KnowledgePoint 模型）
> **预估改动**: ~18 行（修改 app.py + 新建模板）

## 对应 Spec 章节

六、路由设计（GET /teacher/dashboard）/ 七、teacher/dashboard.html

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
    question_count = Question.query.filter_by(teacher_id=current_user.id).count()
    kp_count = KnowledgePoint.query.filter_by(teacher_id=current_user.id).count()
    return render_template("teacher/dashboard.html",
                           exams=exams, question_count=question_count, kp_count=kp_count)
```

### Step 2: 创建 `templates/teacher/dashboard.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>教师仪表盘</h2>

<!-- 快捷操作 -->
<div class="row mb-4">
  <div class="col-md-4">
    <div class="card text-bg-primary text-center p-3">
      <a href="{{ url_for('create_exam_page') }}" class="text-white text-decoration-none">
        <h4>➕ 创建试卷</h4></a>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card text-bg-success text-center p-3">
      <a href="{{ url_for('question_bank') }}" class="text-white text-decoration-none">
        <h4>📦 题库管理</h4><small>{{ question_count }} 道题目</small></a>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card text-bg-info text-center p-3">
      <a href="{{ url_for('knowledge_points_page') }}" class="text-white text-decoration-none">
        <h4>🏷️ 知识点</h4><small>{{ kp_count }} 个标签</small></a>
    </div>
  </div>
</div>

<!-- 试卷列表 -->
<h4>我的试卷</h4>
{% if exams %}
<table class="table table-bordered bg-white">
  <thead><tr><th>试卷名称</th><th>出卷方式</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
  <tbody>{% for e in exams %}
    <tr>
      <td>{{ e.title }}</td>
      <td><span class="badge bg-secondary">{{ e.creation_mode }}</span></td>
      <td>{{ e.status }}</td>
      <td>{{ e.created_at.strftime('%Y-%m-%d %H:%M') }}</td>
      <td><a href="{{ url_for('exam_results', exam_id=e.id) }}" class="btn btn-sm btn-outline-info">查看成绩</a></td>
    </tr>
  {% endfor %}</tbody>
</table>
{% else %}<p>还没有创建任何试卷。</p>{% endif %}
{% endblock %}
```

## 验收标准
- 教师登录后自动跳转到 `/teacher/dashboard`
- 页面显示三个快捷卡片（创建试卷 / 题库管理 / 知识点）+ 试卷列表（当前为空）
- 题库统计和知识点统计均显示 0
- 学生角色访问此页 → 自动重定向到学生仪表盘
