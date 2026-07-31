# Plan 010: Submission 模型 + 提交答案 + 自动阅卷

> **依赖**: Plan 009（答题页提交到此路由）
> **预估改动**: ~30 行（修改 app.py）

## 对应 Spec 章节

三、数据模型（Submission 表）/ 四、功能清单（4. 自动阅卷）/ 六、路由设计（POST /student/exam/<id>/submit）

## 需要修改的文件

1. `exam_maker/app.py` — 添加 Submission 模型 + 提交路由（含自动判分逻辑）

## 改动步骤

### Step 1: 在 `app.py` 中 Exam 模型后添加 Submission 模型

```python
class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    answers_json = db.Column(db.Text, nullable=False, default="{}")
    score = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    exam = db.relationship("Exam", backref="submissions")
```

### Step 2: 在 `app.py` 中添加提交路由（含自动判分）

```python
@app.route("/student/exam/<int:exam_id>/submit", methods=["POST"])
@login_required
def submit_exam(exam_id):
    if current_user.role != "student":
        return redirect(url_for("teacher_dashboard"))
    exam = db.session.get(Exam, exam_id)
    if not exam: return "试卷不存在", 404

    # 收集答案
    questions = json.loads(exam.questions_json)
    answers = {}
    for i in range(len(questions)):
        val = request.form.getlist(f"q{i}")
        answers[str(i)] = val[0] if len(val) == 1 else sorted(val)

    # 自动判分
    score = 0
    per_q = 100 // len(questions) if questions else 0
    for i, q in enumerate(questions):
        student_ans = answers.get(str(i))
        correct = q.get("answer")
        if isinstance(correct, list):
            student_val = sorted(student_ans) if isinstance(student_ans, list) else [student_ans]
            if sorted(correct) == sorted(student_val): score += per_q
        else:
            if str(student_ans).strip().lower() == str(correct).strip().lower(): score += per_q

    sub = Submission(exam_id=exam_id, student_id=current_user.id,
                     answers_json=json.dumps(answers, ensure_ascii=False), score=score)
    db.session.add(sub); db.session.commit()
    return redirect(url_for("exam_result", exam_id=exam_id))
```

## 验收标准
- 学生填完所有题目点"交卷" → 数据库 `submissions` 表新增一条记录
- `answers_json` 正确存储学生答案
- `score` 值由自动判分逻辑计算得出（单选匹配正确 +分，填空中英文大小写忽略）
- 跳转到 `/student/exam/<id>/result`
