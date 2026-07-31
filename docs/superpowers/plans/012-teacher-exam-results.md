# Plan 012: 教师成绩查看页

> **依赖**: Plan 010（Submission 模型存在）
> **预估改动**: ~20 行（修改 app.py + 新建模板）

## 对应 Spec 章节

四、功能清单（2. 教师 AI 出卷 → 查看学生成绩）/ 六、路由设计（GET /teacher/exam/<id>/results）/ 七、teacher/exam_results.html

## 需要创建的文件

1. `exam_maker/templates/teacher/exam_results.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加成绩查看路由

## 改动步骤

### Step 1: 在 `app.py` 中添加

```python
@app.route("/teacher/exam/<int:exam_id>/results")
@login_required
def exam_results(exam_id):
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    exam = db.session.get(Exam, exam_id)
    if not exam or exam.teacher_id != current_user.id:
        return "试卷不存在", 404
    subs = (Submission.query.filter_by(exam_id=exam_id)
            .order_by(Submission.submitted_at.desc()).all())
    return render_template("teacher/exam_results.html", exam=exam, subs=subs)
```

### Step 2: 创建 `templates/teacher/exam_results.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ exam.title }} — 学生成绩</h2>
<a href="{{ url_for('teacher_dashboard') }}" class="btn btn-sm btn-outline-secondary mb-3">← 返回仪表盘</a>
{% if subs %}
<table class="table table-bordered bg-white">
  <thead><tr><th>学生</th><th>得分</th><th>满分</th><th>提交时间</th></tr></thead>
  <tbody>{% for s in subs %}
    <tr><td>{{ s.student_id }}</td><td>{{ s.score }}</td><td>100</td>
      <td>{{ s.submitted_at.strftime('%Y-%m-%d %H:%M') if s.submitted_at else '-' }}</td></tr>
  {% endfor %}</tbody>
</table>
{% else %}<p>暂无学生提交。</p>{% endif %}
{% endblock %}
```

## 验收标准
- 教师在仪表盘点"查看成绩" → 看到该试卷的提交列表
- 表格显示每份提交的：学生 ID、得分、满分、提交时间
- 仅该试卷的教师创建者可查看，其他教师访问返回 404
