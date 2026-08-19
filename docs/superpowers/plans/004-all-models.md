# Plan 004: 核心数据模型 — Exam + KnowledgePoint + Question + 关联表

> **依赖**: Plan 002（User 模型存在）
> **预估改动**: ~30 行（修改 app.py）

## 对应 Spec 章节

三、数据模型（Exam / KnowledgePoint / Question / question_knowledge_points 表）

## 需要修改的文件

1. `exam_maker/app.py` — 在 User 模型之后依次添加 4 个模型

## 改动步骤

### Step 1: 在 `app.py` 的 `from datetime` 导入处统一处理

```python
from datetime import datetime, timezone
```

### Step 2: 在 `app.py` User 类之后，添加 Exam 模型

```python
class Exam(db.Model):
    __tablename__ = "exams"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    creation_mode = db.Column(db.String(16), nullable=False, default="ai_generate")
    # creation_mode: "ai_generate" | "manual_upload" | "difficulty_ratio"
    questions_json = db.Column(db.Text, nullable=False, default="[]")
    status = db.Column(db.String(16), nullable=False, default="draft")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teacher = db.relationship("User", backref="exams")
```

### Step 3: 添加 KnowledgePoint 模型

```python
class KnowledgePoint(db.Model):
    __tablename__ = "knowledge_points"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    __table_args__ = (db.UniqueConstraint("name", "teacher_id", name="uq_kp_name_teacher"),)
    teacher = db.relationship("User", backref="knowledge_points")
```

> `name` + `teacher_id` 联合唯一：同一个教师下知识点名称不可重复，不同教师之间同名知识点互不影响。

### Step 4: 添加 Question 模型（题库）

```python
class Question(db.Model):
    __tablename__ = "questions"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(16), nullable=False)      # single_choice | multi_choice | fill_blank
    question_text = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, nullable=False, default="[]")
    answer = db.Column(db.String(256), nullable=False)
    difficulty = db.Column(db.Integer, nullable=False, default=3)  # 1-5
    source = db.Column(db.String(16), nullable=False, default="manual_upload")  # ai_generate | manual_upload
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teacher = db.relationship("User", backref="questions")
```

### Step 5: 添加题目-知识点关联表

```python
question_knowledge_points = db.Table(
    "question_knowledge_points",
    db.Column("question_id", db.Integer, db.ForeignKey("questions.id"), primary_key=True),
    db.Column("knowledge_point_id", db.Integer, db.ForeignKey("knowledge_points.id"), primary_key=True),
)
```

> 联合主键，多对多关联。通过 `Question` 和 `KnowledgePoint` 的 relationship 访问。

## 验收标准
- `python -c "from app import db, Exam, KnowledgePoint, Question; print(Exam.__tablename__, KnowledgePoint.__tablename__, Question.__tablename__)"` 输出三个表名
- 重新启动应用 → `instance/exam_maker.db` 中自动创建 `exams`、`knowledge_points`、`questions`、`question_knowledge_points` 四张表
