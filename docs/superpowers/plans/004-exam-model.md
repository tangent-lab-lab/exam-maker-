# Plan 004: Exam 模型

> **依赖**: Plan 002（User 模型存在）
> **预估改动**: ~12 行（修改 app.py）

## 对应 Spec 章节

三、数据模型（Exam 表）

## 需要修改的文件

1. `exam_maker/app.py` — 在 User 模型之后添加 Exam 模型

## 改动步骤

### Step 1: 在 `app.py` 中 User 类定义之后添加 Exam 模型

```python
from datetime import datetime, timezone

class Exam(db.Model):
    __tablename__ = "exams"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    questions_json = db.Column(db.Text, nullable=False, default="[]")
    status = db.Column(db.String(16), nullable=False, default="draft")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teacher = db.relationship("User", backref="exams")
```

## 验收标准
- `python -c "from app import db, Exam; print(Exam.__tablename__)"` 输出 `exams`
- 重新启动应用 → `instance/exam_maker.db` 中自动创建 `exams` 表
