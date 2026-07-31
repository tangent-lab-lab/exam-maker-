# Plan 003: 注册 + 登录路由 + 模板

> **依赖**: Plan 002（User 模型）
> **预估改动**: ~30 行（修改 app.py + 新增 2 个模板）

## 对应 Spec 章节

四、功能清单（1. 用户注册/登录）/ 六、路由设计 / 七、login.html / register.html

## 需要创建的文件

1. `exam_maker/templates/login.html`
2. `exam_maker/templates/register.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加 auth 路由

## 改动步骤

### Step 1: 在 `app.py` 末尾（`if __name__` 之前）添加 auth 路由

```python
from flask import render_template, request, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user

@app.route("/")
def index():
    return redirect(url_for("login_page"))

@app.route("/auth/login", methods=["GET"])
def login_page():
    return render_template("login.html")

@app.route("/auth/login", methods=["POST"])
def login():
    user = User.query.filter_by(username=request.form["username"]).first()
    if user and user.check_password(request.form["password"]):
        login_user(user)
        return redirect(url_for("teacher_dashboard" if user.role=="teacher" else "student_dashboard"))
    return render_template("login.html", error="用户名或密码错误")

@app.route("/auth/register", methods=["GET"])
def register_page():
    return render_template("register.html")

@app.route("/auth/register", methods=["POST"])
def register():
    if User.query.filter_by(username=request.form["username"]).first():
        return render_template("register.html", error="用户名已存在")
    user = User(username=request.form["username"], role=request.form.get("role","student"))
    user.set_password(request.form["password"])
    db.session.add(user); db.session.commit()
    login_user(user)
    return redirect(url_for("teacher_dashboard" if user.role=="teacher" else "student_dashboard"))

@app.route("/auth/logout")
def logout():
    logout_user()
    return redirect(url_for("login_page"))
```

### Step 2: 创建 `templates/login.html`

```html
{% extends "base.html" %}
{% block content %}
<div class="card shadow"><div class="card-body">
  <h3 class="text-center mb-3">登录</h3>
  {% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}
  <form method="post">
    <input class="form-control mb-2" name="username" placeholder="用户名" required>
    <input class="form-control mb-2" name="password" type="password" placeholder="密码" required>
    <button class="btn btn-primary w-100" type="submit">登录</button>
  </form>
  <p class="mt-2 text-center"><a href="{{ url_for('register_page') }}">没有账号？去注册</a></p>
</div></div>
{% endblock %}
```

### Step 3: 创建 `templates/register.html`

```html
{% extends "base.html" %}
{% block content %}
<div class="card shadow"><div class="card-body">
  <h3 class="text-center mb-3">注册</h3>
  {% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}
  <form method="post">
    <input class="form-control mb-2" name="username" placeholder="用户名" required>
    <input class="form-control mb-2" name="password" type="password" placeholder="密码" required>
    <select class="form-select mb-2" name="role"><option value="student">学生</option><option value="teacher">教师</option></select>
    <button class="btn btn-success w-100" type="submit">注册</button>
  </form>
  <p class="mt-2 text-center"><a href="{{ url_for('login_page') }}">已有账号？去登录</a></p>
</div></div>
{% endblock %}
```

## 验收标准
- 访问 `/auth/register` → 看到注册表单（用户名、密码、角色下拉框）
- 注册一个教师账号 → 自动登录，跳转到 `/teacher/dashboard`（当前 404，Plan 005 会补）
- 注册一个学生账号 → 跳转到 `/student/dashboard`（同上）
- `/auth/logout` → 回到登录页
- 用已注册账号登录 → 成功跳转
