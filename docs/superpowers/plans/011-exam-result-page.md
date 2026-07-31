# Plan 011: 成绩页 — 显示得分 + 答案对照

> **依赖**: Plan 010（Submission 已保存）
> **预估改动**: ~22 行（修改 app.py + 新建模板）

## 对应 Spec 章节

四、功能清单（4. 自动阅卷 → 成绩页）/ 六、路由设计（GET /student/exam/<id>/result）/ 七、student/result.html

## 需要创建的文件

1. `exam_maker/templates/student/result.html`

## 需要修改的文件

1. `exam_maker/app.py` — 添加成绩查看路由

## 改动步骤

### Step 1: 在 `app.py` 中添加成绩路由

```python
@app.route("/student/exam/<int:exam_id>/result")
@login_required
def exam_result(exam_id):
    if current_user.role != "student":
        return redirect(url_for("teacher_dashboard"))
    sub = Submission.query.filter_by(exam_id=exam_id, student_id=current_user.id).first()
    if not sub: return "未提交", 404
    exam = db.session.get(Exam, exam_id)
    questions = json.loads(exam.questions_json)
    answers = json.loads(sub.answers_json)
    return render_template("student/result.html", exam=exam, sub=sub,
                           questions=questions, answers=answers, zip=zip)
```

### Step 2: 创建 `templates/student/result.html`

```html
{% extends "base.html" %}
{% block content %}
<h2>{{ exam.title }} — 成绩</h2>
<div class="alert alert-info text-center"><h1>{{ sub.score }} / 100</h1></div>
{% for q, ans in zip(questions, answers.values()) %}
<div class="card mb-2">
  <div class="card-body">
    <p><strong>{{ loop.index }}. {{ q.question }}</strong></p>
    <p>你的答案：<span class="{% if q.answer == ans or (q.answer is iterable and q.answer|join(',') == ans|join(',')) %}text-success{% else %}text-danger{% endif %}">{{ ans if ans is string else ans|join(', ') }}</span></p>
    <p class="text-success">正确答案：{{ q.answer if q.answer is string else q.answer|join(', ') }}</p>
  </div>
</div>
{% endfor %}
<a href="{{ url_for('student_dashboard') }}" class="btn btn-primary">返回试卷列表</a>
{% endblock %}
```

## 验收标准
- 交卷后自动跳转到成绩页 → 顶部大字显示总分（如 80/100）
- 每道题显示：你的答案（红色若错 / 绿色若对）+ 正确答案
- 单选匹配正确 → 绿色；填空答案不一致 → 红色
