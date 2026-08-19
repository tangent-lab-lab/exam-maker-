# Plan 012: 提交 + 自动阅卷 + 学生成绩页 + 教师成绩查看

> **依赖**: Plan 011（答题页提交到此路由）
> **预估改动**: ~30 行（修改 app.py + 新建 2 个模板）

## 对应 Spec 章节

三、数据模型（Submission 表）/ 四-6. 自动阅卷 / 六、路由设计 / 七、student/result.html + teacher/exam_results.html

## 需要创建的文件

1. `exam_maker/templates/student/result.html`
2. `exam_maker/templates/teacher/exam_results.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加 Submission 模型 + 提交/阅卷路由 + 学生成绩路由 + 教师成绩查看路由

## 改动步骤

### Step 1: 在 `app.py` 中 Exam 模型之后添加 Submission 模型

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
    student = db.relationship("User", backref="submissions")
```

### Step 2: 在 `app.py` 路由区域添加提交 + 成绩路由

```python
# ========== 提交答案 + 自动阅卷 ==========

@app.route("/student/exam/<int:exam_id>/submit", methods=["POST"])
@login_required
def submit_exam(exam_id):
    if current_user.role != "student":
        return redirect(url_for("teacher_dashboard"))
    exam = db.session.get(Exam, exam_id)
    if not exam:
        return "试卷不存在", 404

    # 收集学生答案
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
            if sorted(correct) == sorted(student_val):
                score += per_q
        else:
            if str(student_ans).strip().lower() == str(correct).strip().lower():
                score += per_q

    sub = Submission(exam_id=exam_id, student_id=current_user.id,
                     answers_json=json.dumps(answers, ensure_ascii=False), score=score)
    db.session.add(sub); db.session.commit()
    return redirect(url_for("exam_result", exam_id=exam_id))


# ========== 学生成绩页 ==========

@app.route("/student/exam/<int:exam_id>/result")
@login_required
def exam_result(exam_id):
    if current_user.role != "student":
        return redirect(url_for("teacher_dashboard"))
    sub = Submission.query.filter_by(exam_id=exam_id, student_id=current_user.id).first()
    if not sub:
        return "未提交", 404
    exam = db.session.get(Exam, exam_id)
    questions = json.loads(exam.questions_json)
    answers = json.loads(sub.answers_json)
    return render_template("student/result.html", exam=exam, sub=sub,
                           questions=questions, answers=answers, zip=zip)


# ========== 教师成绩查看 ==========

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

### Step 3: 创建 `templates/student/result.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ exam.title }} — 成绩</h2>
<div class="alert alert-info text-center"><h1>{{ sub.score }} / 100</h1></div>
{% for q, ans in zip(questions, answers.values()) %}
<div class="card mb-2">
  <div class="card-body">
    <p><strong>{{ loop.index }}. {{ q.question }}</strong></p>
    <p>你的答案：
      <span class="{% if q.answer == ans or (q.answer is iterable and q.answer|join(',') == ans|join(',')) %}text-success{% else %}text-danger{% endif %}">
        {{ ans if ans is string else ans|join(', ') }}
      </span>
    </p>
    <p class="text-success">正确答案：{{ q.answer if q.answer is string else q.answer|join(', ') }}</p>
  </div>
</div>
{% endfor %}
<a href="{{ url_for('student_dashboard') }}" class="btn btn-primary">返回试卷列表</a>
{% endblock %}
```

### Step 4: 创建 `templates/teacher/exam_results.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ exam.title }} — 学生成绩</h2>
<a href="{{ url_for('teacher_dashboard') }}" class="btn btn-sm btn-outline-secondary mb-3">← 返回仪表盘</a>
<p class="text-muted">出卷方式：{{ exam.creation_mode }}</p>
{% if subs %}
<table class="table table-bordered bg-white">
  <thead><tr><th>学生</th><th>得分</th><th>满分</th><th>提交时间</th></tr></thead>
  <tbody>{% for s in subs %}
    <tr><td>{{ s.student.username }}</td><td>{{ s.score }}</td><td>100</td>
      <td>{{ s.submitted_at.strftime('%Y-%m-%d %H:%M') if s.submitted_at else '-' }}</td></tr>
  {% endfor %}</tbody>
</table>
{% else %}<p>暂无学生提交。</p>{% endif %}
{% endblock %}
```

## 验收标准
- 学生填完所有题目点"交卷"→ 数据库 `submissions` 表新增记录，`score` 自动计算
- 跳转到成绩页 → 顶部大字显示分数 + 每道题答案对照（正确绿色/错误红色）
- 教师仪表盘点某试卷"查看成绩"→ 看到学生提交列表（学生用户名、得分、提交时间）
- 三种出卷方式（AI / 上传 / 配比）创建的试卷，学生均能正常答题、阅卷、查看成绩
- 教师仅能查看自己创建的试卷成绩，不能跨教师访问
