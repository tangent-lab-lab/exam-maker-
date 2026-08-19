# Plan 006: 知识点管理 — CRUD + 管理页

> **依赖**: Plan 004（KnowledgePoint 模型）、Plan 005（仪表盘入口）
> **预估改动**: ~25 行（修改 app.py + 新建模板）

## 对应 Spec 章节

四、功能清单（3. 知识点管理）/ 六、路由设计 / 七、teacher/knowledge_points.html

## 需要创建的文件

1. `exam_maker/templates/teacher/knowledge_points.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加知识点管理路由

## 改动步骤

### Step 1: 在 `app.py` 路由区域添加知识点路由

```python
# ========== 知识点管理 ==========

@app.route("/teacher/knowledge_points")
@login_required
def knowledge_points_page():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).order_by(KnowledgePoint.name).all()
    return render_template("teacher/knowledge_points.html", kps=kps)

@app.route("/teacher/knowledge_points/create", methods=["POST"])
@login_required
def create_knowledge_point():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    name = request.form.get("name", "").strip()
    if name:
        existing = KnowledgePoint.query.filter_by(name=name, teacher_id=current_user.id).first()
        if not existing:
            kp = KnowledgePoint(name=name, teacher_id=current_user.id)
            db.session.add(kp); db.session.commit()
    return redirect(url_for("knowledge_points_page"))

@app.route("/teacher/knowledge_points/<int:kp_id>/edit", methods=["POST"])
@login_required
def edit_knowledge_point(kp_id):
    kp = KnowledgePoint.query.filter_by(id=kp_id, teacher_id=current_user.id).first()
    if kp:
        name = request.form.get("name", "").strip()
        if name:
            kp.name = name; db.session.commit()
    return redirect(url_for("knowledge_points_page"))

@app.route("/teacher/knowledge_points/<int:kp_id>/delete", methods=["POST"])
@login_required
def delete_knowledge_point(kp_id):
    kp = KnowledgePoint.query.filter_by(id=kp_id, teacher_id=current_user.id).first()
    if kp:
        # 先清理关联表中引用此知识点的记录
        db.session.execute(
            question_knowledge_points.delete().where(
                question_knowledge_points.c.knowledge_point_id == kp_id
            )
        )
        db.session.delete(kp); db.session.commit()
    return redirect(url_for("knowledge_points_page"))
```

### Step 2: 创建 `templates/teacher/knowledge_points.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>🏷️ 知识点管理</h2>
<a href="{{ url_for('teacher_dashboard') }}" class="btn btn-sm btn-outline-secondary mb-3">← 返回仪表盘</a>

<!-- 新建知识点 -->
<div class="card mb-4"><div class="card-body">
  <form method="post" action="{{ url_for('create_knowledge_point') }}" class="row g-2">
    <div class="col-8"><input class="form-control" name="name" placeholder="输入知识点名称，如：一元二次方程" required></div>
    <div class="col-4"><button type="submit" class="btn btn-primary w-100">添加</button></div>
  </form>
</div></div>

<!-- 知识点列表 -->
{% if kps %}
<table class="table table-bordered bg-white">
  <thead><tr><th>名称</th><th style="width:200px">操作</th></tr></thead>
  <tbody>
  {% for kp in kps %}
  <tr>
    <td>
      <span class="me-2" id="kp-name-{{ kp.id }}">{{ kp.name }}</span>
      <form method="post" action="{{ url_for('edit_knowledge_point', kp_id=kp.id) }}" class="d-none" id="kp-edit-{{ kp.id }}">
        <input class="form-control form-control-sm d-inline w-50" name="name" value="{{ kp.name }}">
        <button type="submit" class="btn btn-sm btn-success">保存</button>
      </form>
    </td>
    <td>
      <button class="btn btn-sm btn-outline-warning" onclick="document.getElementById('kp-name-{{ kp.id }}').classList.add('d-none');document.getElementById('kp-edit-{{ kp.id }}').classList.remove('d-none')">编辑</button>
      <form method="post" action="{{ url_for('delete_knowledge_point', kp_id=kp.id) }}" style="display:inline"
            onsubmit="return confirm('删除知识点「{{ kp.name }}」将同时取消所有题目与该知识点的关联，确定删除？')">
        <button class="btn btn-sm btn-outline-danger">删除</button>
      </form>
    </td>
  </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}<p>暂无知识点，请先添加。</p>{% endif %}
{% endblock %}
```

## 验收标准
- 教师进入 `/teacher/knowledge_points` → 看到知识点管理页
- 输入"一元二次方程"点添加 → 列表中出现该知识点
- 编辑知识点名称 → 更新成功
- 删除知识点 → 确认后删除
- 同名知识点不可重复添加
