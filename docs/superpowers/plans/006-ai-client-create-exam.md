# Plan 006: AI 客户端 + 出卷 POST 路由

> **依赖**: Plan 004（Exam 模型）、Plan 005（教师仪表盘）
> **预估改动**: ~25 行（修改 app.py）

## 对应 Spec 章节

五、AI 出卷提示词逻辑 / 四、功能清单（2. 教师 AI 出卷）/ 六、路由设计（POST /teacher/create_exam）

## 需要修改的文件

1. `exam_maker/app.py` — 添加 AI 调用函数 + 出卷 POST 路由

## 改动步骤

### Step 1: 在 `app.py` 的 `load_dotenv()` 之后、Flask app 初始化之前，添加 AI 调用函数

```python
import httpx

def call_llm(prompt: str) -> str:
    resp = httpx.post(
        f"{os.getenv('LLM_BASE_URL')}/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('LLM_API_KEY')}"},
        json={"model": os.getenv("LLM_MODEL"), "messages": [{"role":"user","content":prompt}]},
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
```

### Step 2: 在 `app.py` 路由区域添加出卷 POST 路由

```python
@app.route("/teacher/create_exam", methods=["POST"])
@login_required
def create_exam():
    if current_user.role != "teacher":
        return redirect(url_for("student_dashboard"))
    title = request.form["title"]
    count = int(request.form["count"])
    difficulty = request.form["difficulty"]
    qtypes = request.form.getlist("qtypes")  # e.g. ["single","multiple","fill"]
    score_per_q = 100 // count

    prompt = (
        f"你是一个出题助手。请生成{count}道题目，难度{difficulty}/5，题型包含{','.join(qtypes)}。"
        f"每题包含：type(题型:single/multiple/fill),question(题干),options(选项列表,非选择题为空数组[]),answer(正确答案)。"
        f"每题{score_per_q}分。只返回JSON数组，不要任何其他内容。"
    )

    try:
        raw = call_llm(prompt)
        questions = json.loads(raw.strip().removeprefix("```json").removesuffix("```"))
    except Exception as e:
        return render_template("teacher/create_exam.html", error=f"AI 出卷失败: {e}")

    exam = Exam(title=title, teacher_id=current_user.id,
                questions_json=json.dumps(questions, ensure_ascii=False), status="published")
    db.session.add(exam); db.session.commit()
    return redirect(url_for("teacher_dashboard"))
```

## 验收标准
- 教师登录后用 curl 或 Postman 发送 `POST /teacher/create_exam` 请求体 `title=测试&count=3&difficulty=3&qtypes=single&qtypes=multiple`
- 数据库 `exams` 表中出现一条记录，`questions_json` 包含 AI 返回的 JSON 题目数组
- 响应 302 重定向到 `/teacher/dashboard`
