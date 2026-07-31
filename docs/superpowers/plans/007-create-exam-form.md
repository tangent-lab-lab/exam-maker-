# Plan 007: 出卷表单页 — GET 路由 + 模板

> **依赖**: Plan 006（POST 出卷路由已就绪）
> **预估改动**: ~18 行（修改 app.py + 新建模板）

## 对应 Spec 章节

六、路由设计（GET /teacher/create_exam）/ 七、teacher/create_exam.html

## 需要创建的文件

1. `exam_maker/templates/teacher/create_exam.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加出卷表单 GET 路由

## 改动步骤

### Step 1: 在 `app.py` 中添加 GET 路由（放在出卷 POST 路由前面）

```python
@app.route("/teacher/create_exam", methods=["GET"])
@login_required
def create_exam_page():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    return render_template("teacher/create_exam.html")
```

### Step 2: 创建 `templates/teacher/create_exam.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>AI 出卷</h2>
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
  <button type="submit" class="btn btn-primary w-100">生成试卷</button>
</form></div>
{% endblock %}
```

## 验收标准
- 教师登录后点仪表盘的"创建试卷"按钮 → 跳转到 `/teacher/create_exam`
- 页面显示：标题输入框 + 数量下拉 + 难易度 radio + 题型 checkbox + 生成按钮
- 填好参数点"生成" → 等待 5-15 秒 → 自动跳回仪表盘 → 看到新试卷出现
