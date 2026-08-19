# Plan 001: 项目骨架 — 依赖 + app 入口 + 基础模板

> **依赖**: 无
> **预估改动**: ~25 行（全部新增）

## 对应 Spec 章节

一、技术栈 / 二、项目文件结构

## 需要创建的文件

1. `exam_maker/requirements.txt`
2. `exam_maker/.env.example`
3. `exam_maker/app.py`（Flask 入口 + 配置 + DB 初始化）
4. `exam_maker/templates/base.html`
5. `exam_maker/static/style.css`

## 改动步骤

### Step 1: 创建 `requirements.txt`

```
flask==3.1.*
flask-sqlalchemy==3.1.*
flask-login==0.6.*
httpx==0.28.*
python-dotenv==1.1.*
python-docx==1.1.*
PyPDF2==3.0.*
```

> `python-docx` 用于解析 Word 文件，`PyPDF2` 用于解析 PDF 文件，两者服务于手动上传出卷功能（Plan 008）。

### Step 2: 创建 `.env.example`

```
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-your-key
LLM_MODEL=deepseek-chat
SECRET_KEY=change-me-in-production
```

### Step 3: 创建 `app.py`

```python
import os, json
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/exam_maker.db"
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login_page"

if __name__ == "__main__":
    import os; os.makedirs("instance", exist_ok=True)
    with app.app_context(): db.create_all()
    app.run(debug=True)
```

### Step 4: 创建 `templates/base.html`

```html
<!DOCTYPE html><html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Exam-Maker</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="{{ url_for('static',filename='style.css') }}"></head>
<body>
<nav class="navbar navbar-expand navbar-dark bg-primary px-3">
  <a class="navbar-brand" href="/">📝 Exam-Maker</a>
  <div class="navbar-nav ms-auto">
    {% if current_user.is_authenticated %}
      <span class="nav-link text-white">{{ current_user.username }}({{ current_user.role }})</span>
      <a class="nav-link" href="{{ url_for('logout') }}">登出</a>
    {% endif %}
  </div>
</nav>
<div class="container mt-4">{% block content %}{% endblock %}</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>
```

### Step 5: 创建 `static/style.css`

```css
body { background: #f5f7fa; }
.card { max-width: 600px; margin: 80px auto; }
.card-wide { max-width: 900px; margin: 40px auto; }
```

## 验收标准
- `cd exam_maker && pip install -r requirements.txt && python app.py` 启动成功
- 浏览器访问 `http://localhost:5000` 不报错（此时无路由，显示 404 是正常的）
- `instance/exam_maker.db` 文件自动生成
