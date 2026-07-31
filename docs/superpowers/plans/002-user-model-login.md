# Plan 002: User 模型 + Flask-Login 集成

> **依赖**: Plan 001（app.py 已创建）
> **预估改动**: ~20 行（修改 app.py）

## 对应 Spec 章节

三、数据模型（User 表）/ 一、认证

## 需要修改的文件

1. `exam_maker/app.py` — 添加 User 模型 + user_loader

## 改动步骤

### Step 1: 在 `app.py` 的 `db = SQLAlchemy(app)` 之后，添加 User 模型

```python
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="student")  # teacher | student

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
```

### Step 2: 在 `login_manager = LoginManager(app)` 之后，添加 user_loader

```python
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
```

### Step 3: 更新 `requirements.txt`，确认已有 `werkzeug` 相关依赖（flask 自带，无需额外添加）

## 验收标准
- `python -c "from app import db, User; print(User.__tablename__)"` 输出 `users`
- 启动应用无报错
