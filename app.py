print("hello"
import os
import json
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import httpx
import random
import secrets

load_dotenv()

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")


def call_llm(prompt: str) -> str:
    """Call LLM API and return response content."""
    resp = httpx.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}]},
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def extract_text(file):
    """Extract text from uploaded file based on extension."""
    filename = file.filename.lower()
    if filename.endswith(".txt"):
        return file.read().decode("utf-8")
    elif filename.endswith(".docx"):
        from docx import Document
        doc = Document(file)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    elif filename.endswith(".pdf"):
        from PyPDF2 import PdfReader
        reader = PdfReader(file)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        raise ValueError("不支持的文件格式，仅支持 .docx / .pdf / .txt")


def parse_datetime_local(value):
    """Parse a datetime-local input value to a naive datetime, or None."""
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


def apply_exam_time_fields(exam):
    """Read start/end/duration from request.form and assign onto exam."""
    exam.start_time = parse_datetime_local(request.form.get("start_time"))
    exam.end_time = parse_datetime_local(request.form.get("end_time"))
    dur = (request.form.get("duration_minutes") or "").strip()
    exam.duration_minutes = int(dur) if dur else None


def grade_subjective(question_text, reference_answer, student_answer, full_score):
    """Call LLM to grade a subjective question; return (score:int, reason:str)."""
    prompt = (
        "你是一名严格的阅卷老师，请批改下面这道主观题。\n"
        f"题目：{question_text}\n"
        f"参考答案：{reference_answer}\n"
        f"学生答案：{student_answer}\n"
        f"满分分值：{full_score}\n\n"
        "请根据学生答案与参考答案的匹配程度，给出 0 到满分之间的得分（整数）和评分理由。\n"
        '只返回 JSON，格式：{"score": 数字, "reason": "评分理由"}，不要任何其他内容。'
    )
    try:
        raw = call_llm(prompt)
        text = raw.strip()
        if text.startswith("```"):
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(text)
        score = int(round(float(data.get("score", 0))))
        score = max(0, min(int(full_score), score))
        reason = str(data.get("reason", "")).strip()
        return score, reason
    except Exception as e:
        return 0, f"AI 批改失败: {e}"


def compute_score(questions, answers, grading):
    """Compute total score from questions, student answers and grading dict."""
    score = 0
    per_q = 100 // len(questions) if questions else 0
    for i, q in enumerate(questions):
        key = str(i)
        if q.get("type") == "subjective":
            g = grading.get(key, {})
            final = g.get("manual_score", g.get("ai_score", 0))
            score += int(final)
        else:
            student_ans = answers.get(key)
            correct = q.get("answer")
            if isinstance(correct, list):
                student_val = sorted(student_ans) if isinstance(student_ans, list) else [student_ans]
                if sorted(correct) == sorted(student_val):
                    score += per_q
            else:
                if str(student_ans).strip().lower() == str(correct).strip().lower():
                    score += per_q
    return score


basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'instance', 'exam_maker.db')}"
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login_page"


# ── Models ──────────────────────────────────────────────

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="student")  # teacher | student
    email = db.Column(db.String(128), default="")
    real_name = db.Column(db.String(128), default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


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
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)

    teacher = db.relationship("User", backref="exams")


class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    answers_json = db.Column(db.Text, nullable=False, default="{}")
    grading_json = db.Column(db.Text, nullable=False, default="{}")
    score = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    exam = db.relationship("Exam", backref="submissions")
    student = db.relationship("User", backref="submissions")


class KnowledgePoint(db.Model):
    __tablename__ = "knowledge_points"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    __table_args__ = (db.UniqueConstraint("name", "teacher_id", name="uq_kp_name_teacher"),)
    teacher = db.relationship("User", backref="knowledge_points")


class Question(db.Model):
    __tablename__ = "questions"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(16), nullable=False)      # single_choice | multi_choice | fill_blank
    question_text = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, nullable=False, default="[]")
    answer = db.Column(db.String(256), nullable=False)
    difficulty = db.Column(db.Integer, nullable=False, default=3)  # 1-5
    source = db.Column(db.String(16), nullable=False, default="manual_upload")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teacher = db.relationship("User", backref="questions")


question_knowledge_points = db.Table(
    "question_knowledge_points",
    db.Column("question_id", db.Integer, db.ForeignKey("questions.id"), primary_key=True),
    db.Column("knowledge_point_id", db.Integer, db.ForeignKey("knowledge_points.id"), primary_key=True),
)


class SchoolClass(db.Model):
    __tablename__ = "classes"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(256), default="")
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    invite_code = db.Column(db.String(16), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teacher = db.relationship("User", backref="classes")
    students = db.relationship("User", secondary="class_student", lazy="dynamic")


class_student = db.Table(
    "class_student",
    db.Column("class_id", db.Integer, db.ForeignKey("classes.id"), primary_key=True),
    db.Column("student_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("joined_at", db.DateTime, default=lambda: datetime.now(timezone.utc)),
)


class_exam = db.Table(
    "class_exam",
    db.Column("class_id", db.Integer, db.ForeignKey("classes.id"), primary_key=True),
    db.Column("exam_id", db.Integer, db.ForeignKey("exams.id"), primary_key=True),
)


def generate_invite_code():
    """Generate a unique 6-char uppercase invite code."""
    while True:
        code = secrets.token_hex(3).upper()
        if not SchoolClass.query.filter_by(invite_code=code).first():
            return code


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ── Auth Routes ─────────────────────────────────────────

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
        return redirect("/teacher/dashboard" if user.role == "teacher" else "/student/dashboard")
    return render_template("login.html", error="用户名或密码错误")


@app.route("/auth/register", methods=["GET"])
def register_page():
    return render_template("register.html")


@app.route("/auth/register", methods=["POST"])
def register():
    if User.query.filter_by(username=request.form["username"]).first():
        return render_template("register.html", error="用户名已存在")
    user = User(username=request.form["username"], role=request.form.get("role", "student"))
    user.set_password(request.form["password"])
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return redirect("/teacher/dashboard" if user.role == "teacher" else "/student/dashboard")


@app.route("/auth/logout")
def logout():
    logout_user()
    return redirect(url_for("login_page"))


# ── User Profile Routes ────────────────────────────────

@app.route("/user/profile", methods=["GET", "POST"])
@login_required
def user_profile():
    user = current_user
    error = None
    success = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_info":
            user.email = request.form.get("email", "").strip()
            user.real_name = request.form.get("real_name", "").strip()
            db.session.commit()
            success = "个人信息已更新"

        elif action == "change_password":
            old_pwd = request.form.get("old_password", "")
            new_pwd = request.form.get("new_password", "")
            confirm_pwd = request.form.get("confirm_password", "")
            if not user.check_password(old_pwd):
                error = "旧密码不正确"
            elif len(new_pwd) < 6:
                error = "新密码至少 6 位"
            elif new_pwd != confirm_pwd:
                error = "两次输入的新密码不一致"
            else:
                user.set_password(new_pwd)
                db.session.commit()
                success = "密码已修改"

    return render_template("profile.html", user=user, error=error, success=success)


# ── Teacher Routes ──────────────────────────────────────

@app.route("/teacher/dashboard")
@login_required
def teacher_dashboard():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    exams = Exam.query.filter_by(teacher_id=current_user.id).order_by(Exam.created_at.desc()).all()
    question_count = Question.query.filter_by(teacher_id=current_user.id).count()
    kp_count = KnowledgePoint.query.filter_by(teacher_id=current_user.id).count()
    return render_template("teacher/dashboard.html",
                           exams=exams, question_count=question_count, kp_count=kp_count)


# ── Knowledge Point Routes ─────────────────────────────

@app.route("/teacher/knowledge_points")
@login_required
def knowledge_points_page():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).order_by(KnowledgePoint.name).all()
    return render_template("teacher/knowledge_points.html", kps=kps)


@app.route("/teacher/knowledge_points/create", methods=["POST"])
@login_required
def create_knowledge_point():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    name = request.form.get("name", "").strip()
    if name:
        existing = KnowledgePoint.query.filter_by(name=name, teacher_id=current_user.id).first()
        if not existing:
            kp = KnowledgePoint(name=name, teacher_id=current_user.id)
            db.session.add(kp)
            db.session.commit()
    return redirect("/teacher/knowledge_points")


@app.route("/teacher/knowledge_points/<int:kp_id>/edit", methods=["POST"])
@login_required
def edit_knowledge_point(kp_id):
    kp = KnowledgePoint.query.filter_by(id=kp_id, teacher_id=current_user.id).first()
    if kp:
        name = request.form.get("name", "").strip()
        if name:
            kp.name = name
            db.session.commit()
    return redirect("/teacher/knowledge_points")


@app.route("/teacher/knowledge_points/<int:kp_id>/delete", methods=["POST"])
@login_required
def delete_knowledge_point(kp_id):
    kp = KnowledgePoint.query.filter_by(id=kp_id, teacher_id=current_user.id).first()
    if kp:
        db.session.execute(
            question_knowledge_points.delete().where(
                question_knowledge_points.c.knowledge_point_id == kp_id
            )
        )
        db.session.delete(kp)
        db.session.commit()
    return redirect("/teacher/knowledge_points")


# ── Exam Creation: Mode Selection ──────────────────────

@app.route("/teacher/create_exam")
@login_required
def create_exam_page():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    return render_template("teacher/create_exam.html")


# ── Exam Creation: AI Generation ───────────────────────

@app.route("/teacher/create_exam/ai", methods=["GET", "POST"])
@login_required
def create_exam_ai():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    if request.method == "GET":
        return render_template("teacher/create_exam_ai.html")

    title = request.form["title"]
    count = int(request.form["count"])
    difficulty = request.form["difficulty"]
    qtypes = request.form.getlist("qtypes")
    save_to_bank = request.form.get("save_to_bank") == "1"

    prompt = (
        f"你是一个出题助手。请生成{count}道题目，难度{difficulty}/5，题型包含{','.join(qtypes)}。"
        f"每题包含：type(题型:single/multiple/fill/subjective),question(题干),"
        f"options(选项列表,非选择题为空数组[]),answer(正确答案,主观题为参考答案),difficulty(难度1-5)。"
        f"只返回JSON数组，不要任何其他内容。"
    )

    try:
        raw = call_llm(prompt)
        questions = json.loads(raw.strip().removeprefix("```json").removesuffix("```"))
    except Exception as e:
        return render_template("teacher/create_exam_ai.html", error=f"AI 出卷失败: {e}")

    # 创建试卷
    exam = Exam(title=title, teacher_id=current_user.id,
                creation_mode="ai_generate",
                questions_json=json.dumps(questions, ensure_ascii=False),
                status="published")
    apply_exam_time_fields(exam)
    db.session.add(exam)
    db.session.commit()

    # 可选：存入题库
    if save_to_bank:
        for q in questions:
            question = Question(
                teacher_id=current_user.id,
                type=q.get("type", "single"),
                question_text=q.get("question", ""),
                options_json=json.dumps(q.get("options", []), ensure_ascii=False),
                answer=str(q.get("answer", "")),
                difficulty=int(q.get("difficulty", difficulty)),
                source="ai_generate",
            )
            db.session.add(question)
        db.session.commit()

    return redirect("/teacher/dashboard")


# ── Exam Creation: Manual Upload ───────────────────────

@app.route("/teacher/create_exam/upload", methods=["GET", "POST"])
@login_required
def create_exam_upload():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    if request.method == "GET":
        kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()
        return render_template("teacher/create_exam_upload.html", kps=kps)

    # POST: upload file + LLM parse
    title = request.form.get("title", "").strip()
    file = request.files.get("file")
    if not file or not title:
        kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()
        return render_template("teacher/create_exam_upload.html", kps=kps, error="请填写标题并选择文件")

    try:
        text = extract_text(file)
    except ValueError as e:
        kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()
        return render_template("teacher/create_exam_upload.html", kps=kps, error=str(e))

    prompt = (
        "你是一个试卷解析助手。以下是从上传文件中提取的文本内容，请将其中的题目结构化。\n"
        "每道题包含：type(题型:single/multiple/fill/subjective),question(题干),"
        "options(选项列表,非选择题为空数组[]),answer(正确答案,主观题为参考答案),"
        "difficulty(难度1-5,根据题目复杂度自行判断)。\n"
        "只返回 JSON 数组，不要任何其他内容。\n\n文本内容：\n" + text[:6000]
    )

    try:
        raw = call_llm(prompt)
        questions = json.loads(raw.strip().removeprefix("```json").removesuffix("```"))
    except Exception as e:
        kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()
        return render_template("teacher/create_exam_upload.html", kps=kps,
                               error=f"AI 解析失败: {e}")

    # Store in session for preview
    session["preview_title"] = title
    session["preview_questions"] = json.dumps(questions, ensure_ascii=False)
    session["preview_kp_ids"] = request.form.getlist("kp_ids")
    session["preview_start_time"] = request.form.get("start_time", "")
    session["preview_end_time"] = request.form.get("end_time", "")
    session["preview_duration_minutes"] = request.form.get("duration_minutes", "")
    return redirect("/teacher/create_exam/upload/preview")


@app.route("/teacher/create_exam/upload/preview")
@login_required
def create_exam_upload_preview():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    title = session.get("preview_title", "")
    questions = json.loads(session.get("preview_questions", "[]"))
    if not questions:
        return redirect("/teacher/create_exam/upload")
    return render_template("teacher/create_exam_upload_preview.html", title=title, questions=questions)


@app.route("/teacher/create_exam/upload/confirm", methods=["POST"])
@login_required
def create_exam_upload_confirm():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    title = session.get("preview_title", "未命名试卷")
    questions_json = session.get("preview_questions", "[]")
    kp_ids_raw = session.get("preview_kp_ids", [])
    questions = json.loads(questions_json)

    # Save questions to bank
    for q in questions:
        question = Question(
            teacher_id=current_user.id,
            type=q.get("type", "single"),
            question_text=q.get("question", ""),
            options_json=json.dumps(q.get("options", []), ensure_ascii=False),
            answer=str(q.get("answer", "")),
            difficulty=int(q.get("difficulty", 3)),
            source="manual_upload",
        )
        db.session.add(question)
        db.session.flush()  # get question.id
        for kp_id in kp_ids_raw:
            db.session.execute(
                question_knowledge_points.insert().values(
                    question_id=question.id, knowledge_point_id=int(kp_id)
                )
            )
    db.session.commit()

    # Create exam
    exam = Exam(title=title, teacher_id=current_user.id,
                creation_mode="manual_upload",
                questions_json=questions_json, status="published")
    exam.start_time = parse_datetime_local(session.get("preview_start_time"))
    exam.end_time = parse_datetime_local(session.get("preview_end_time"))
    dur = (session.get("preview_duration_minutes") or "").strip()
    exam.duration_minutes = int(dur) if dur else None
    db.session.add(exam)
    db.session.commit()

    # Clear session
    session.pop("preview_title", None)
    session.pop("preview_questions", None)
    session.pop("preview_kp_ids", None)
    session.pop("preview_start_time", None)
    session.pop("preview_end_time", None)
    session.pop("preview_duration_minutes", None)
    return redirect("/teacher/dashboard")


@app.route("/teacher/create_exam/upload/cancel", methods=["POST"])
@login_required
def create_exam_upload_cancel():
    session.pop("preview_title", None)
    session.pop("preview_questions", None)
    session.pop("preview_kp_ids", None)
    session.pop("preview_start_time", None)
    session.pop("preview_end_time", None)
    session.pop("preview_duration_minutes", None)
    return redirect("/teacher/create_exam/upload")


# ── Question Bank Management ───────────────────────────

@app.route("/teacher/question_bank")
@login_required
def question_bank():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")

    kp_filter = request.args.get("kp", type=int)
    difficulty_filter = request.args.get("difficulty", type=int)
    type_filter = request.args.get("type", "")

    query = Question.query.filter_by(teacher_id=current_user.id)
    if difficulty_filter:
        query = query.filter_by(difficulty=difficulty_filter)
    if type_filter:
        query = query.filter_by(type=type_filter)
    if kp_filter:
        query = query.join(question_knowledge_points).filter(
            question_knowledge_points.c.knowledge_point_id == kp_filter
        )

    questions = query.order_by(Question.created_at.desc()).all()
    kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()

    # Preload knowledge points for each question
    q_with_kps = []
    for q in questions:
        kp_ids = [r[0] for r in db.session.execute(
            db.select(question_knowledge_points.c.knowledge_point_id).where(
                question_knowledge_points.c.question_id == q.id
            )
        ).fetchall()]
        q_kps = KnowledgePoint.query.filter(KnowledgePoint.id.in_(kp_ids)).all() if kp_ids else []
        q_with_kps.append((q, q_kps))

    return render_template("teacher/question_bank.html",
                           questions=q_with_kps, kps=kps,
                           kp_filter=kp_filter, difficulty_filter=difficulty_filter,
                           type_filter=type_filter)


@app.route("/teacher/question/<int:q_id>/edit", methods=["POST"])
@login_required
def edit_question(q_id):
    q = Question.query.filter_by(id=q_id, teacher_id=current_user.id).first()
    if not q:
        return redirect("/teacher/question_bank")
    q.question_text = request.form.get("question_text", q.question_text)
    q.type = request.form.get("type", q.type)
    q.options_json = request.form.get("options_json", q.options_json)
    q.answer = request.form.get("answer", str(q.answer))
    q.difficulty = int(request.form.get("difficulty", q.difficulty))

    # Update knowledge point associations
    kp_ids = request.form.getlist("kp_ids")
    db.session.execute(
        question_knowledge_points.delete().where(
            question_knowledge_points.c.question_id == q.id
        )
    )
    for kp_id in kp_ids:
        db.session.execute(
            question_knowledge_points.insert().values(
                question_id=q.id, knowledge_point_id=int(kp_id)
            )
        )
    db.session.commit()
    return redirect("/teacher/question_bank")


@app.route("/teacher/question/<int:q_id>/delete", methods=["POST"])
@login_required
def delete_question(q_id):
    q = Question.query.filter_by(id=q_id, teacher_id=current_user.id).first()
    if q:
        db.session.execute(
            question_knowledge_points.delete().where(
                question_knowledge_points.c.question_id == q.id
            )
        )
        db.session.delete(q)
        db.session.commit()
    return redirect("/teacher/question_bank")


# ── Exam Creation: Difficulty Ratio ────────────────────

@app.route("/teacher/create_exam/ratio", methods=["GET", "POST"])
@login_required
def create_exam_ratio():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")

    kps = KnowledgePoint.query.filter_by(teacher_id=current_user.id).all()

    if request.method == "GET":
        available = Question.query.filter_by(teacher_id=current_user.id).count()
        return render_template("teacher/create_exam_ratio.html", kps=kps, available=available)

    # POST: draw by ratio
    title = request.form.get("title", "").strip()
    total = int(request.form.get("total", 10))
    qtypes = request.form.getlist("qtypes")
    ratio_easy = int(request.form.get("ratio_easy", 3))
    ratio_medium = int(request.form.get("ratio_medium", 5))
    ratio_hard = int(request.form.get("ratio_hard", 2))
    kp_filter = request.form.get("kp_filter", type=int)
    available = Question.query.filter_by(teacher_id=current_user.id).count()

    # Calculate needed counts per difficulty bracket
    ratio_sum = ratio_easy + ratio_medium + ratio_hard
    need = {
        "easy": round(total * ratio_easy / ratio_sum),    # difficulty 1-2
        "medium": round(total * ratio_medium / ratio_sum), # difficulty 3
        "hard": round(total * ratio_hard / ratio_sum),     # difficulty 4-5
    }
    need["hard"] = total - need["easy"] - need["medium"]  # ensure exact total

    # Difficulty ranges
    ranges = {"easy": (1, 2), "medium": (3, 3), "hard": (4, 5)}

    def get_kp_ids_for_question(q):
        """Return list of knowledge_point_ids linked to a question."""
        rows = db.session.execute(
            db.select(question_knowledge_points.c.knowledge_point_id).where(
                question_knowledge_points.c.question_id == q.id
            )
        ).fetchall()
        return {r[0] for r in rows}

    # Check availability and draw
    errors = []
    selected = []
    for bracket, req in need.items():
        if req <= 0:
            continue
        lo, hi = ranges[bracket]
        pool = Question.query.filter_by(teacher_id=current_user.id)
        pool = pool.filter(Question.difficulty >= lo, Question.difficulty <= hi)
        if qtypes:
            pool = pool.filter(Question.type.in_(qtypes))
        pool = pool.all()

        if kp_filter:
            pool = [q for q in pool if kp_filter in get_kp_ids_for_question(q)]

        if len(pool) < req:
            errors.append(f"{bracket}题(难度{lo}-{hi})不足：需要 {req} 道，当前仅 {len(pool)} 道")
        else:
            random.shuffle(pool)
            selected.extend(pool[:req])

    if errors:
        return render_template("teacher/create_exam_ratio.html", kps=kps, available=available,
                               error="; ".join(errors))

    if len(selected) < total:
        return render_template("teacher/create_exam_ratio.html", kps=kps, available=available,
                               error=f"符合条件的题目不足：需要 {total} 道，仅匹配到 {len(selected)} 道")

    # Assemble questions_json
    questions_json = []
    for q in selected[:total]:
        questions_json.append({
            "type": q.type,
            "question": q.question_text,
            "options": json.loads(q.options_json),
            "answer": q.answer,
            "difficulty": q.difficulty,
        })

    exam = Exam(title=title, teacher_id=current_user.id,
                creation_mode="difficulty_ratio",
                questions_json=json.dumps(questions_json, ensure_ascii=False),
                status="published")
    apply_exam_time_fields(exam)
    db.session.add(exam)
    db.session.commit()
    return redirect("/teacher/dashboard")


# ── Student Routes ──────────────────────────────────────

@app.route("/student/dashboard")
@login_required
def student_dashboard():
    if current_user.role != "student":
        return redirect("/teacher/dashboard")
    exams = Exam.query.filter_by(status="published").order_by(Exam.created_at.desc()).all()
    return render_template("student/dashboard.html", exams=exams)


@app.route("/student/exam/<int:exam_id>")
@login_required
def take_exam(exam_id):
    if current_user.role != "student":
        return redirect("/teacher/dashboard")
    exam = db.session.get(Exam, exam_id)
    if not exam or exam.status != "published":
        return "试卷不存在", 404
    questions = json.loads(exam.questions_json)

    now = datetime.now()
    start_time = exam.start_time
    end_time = exam.end_time
    duration = exam.duration_minutes

    # 计算有效截止时间（取结束时间与「开始时间+时长」中较早者）
    deadline = end_time
    if duration:
        base = start_time if start_time else now
        dur_deadline = base + timedelta(minutes=duration)
        deadline = dur_deadline if deadline is None else min(deadline, dur_deadline)

    not_started = start_time is not None and now < start_time
    ended = deadline is not None and now >= deadline

    countdown_seconds = None
    if not not_started and not ended and deadline is not None:
        countdown_seconds = int((deadline - now).total_seconds())

    return render_template("student/take_exam.html", exam=exam, questions=questions,
                           not_started=not_started, ended=ended,
                           countdown_seconds=countdown_seconds)


# ── Student: Submit + Auto-Grade ────────────────────────

@app.route("/student/exam/<int:exam_id>/submit", methods=["POST"])
@login_required
def submit_exam(exam_id):
    if current_user.role != "student":
        return redirect("/teacher/dashboard")
    exam = db.session.get(Exam, exam_id)
    if not exam:
        return "试卷不存在", 404

    now = datetime.now()
    if exam.start_time and now < exam.start_time:
        return "考试尚未开始，无法提交", 403
    if exam.end_time and now > exam.end_time:
        return "考试已结束，无法提交", 403

    # Collect student answers
    questions = json.loads(exam.questions_json)
    answers = {}
    for i in range(len(questions)):
        val = request.form.getlist(f"q{i}")
        answers[str(i)] = val[0] if len(val) == 1 else sorted(val)

    # Auto-grade objective + AI-grade subjective
    grading = {}
    per_q = 100 // len(questions) if questions else 0
    for i, q in enumerate(questions):
        if q.get("type") == "subjective":
            student_ans = answers.get(str(i))
            ans_text = student_ans if isinstance(student_ans, str) else (
                " ".join(student_ans) if isinstance(student_ans, list) else "")
            ai_score, ai_reason = grade_subjective(
                q.get("question", ""), str(q.get("answer", "")), ans_text, per_q)
            grading[str(i)] = {"ai_score": ai_score, "ai_reason": ai_reason}

    score = compute_score(questions, answers, grading)

    sub = Submission(exam_id=exam_id, student_id=current_user.id,
                     answers_json=json.dumps(answers, ensure_ascii=False),
                     grading_json=json.dumps(grading, ensure_ascii=False),
                     score=score)
    db.session.add(sub)
    db.session.commit()
    return redirect(f"/student/exam/{exam_id}/result")


# ── Student: Result Page ────────────────────────────────

@app.route("/student/exam/<int:exam_id>/result")
@login_required
def exam_result(exam_id):
    if current_user.role != "student":
        return redirect("/teacher/dashboard")
    sub = Submission.query.filter_by(exam_id=exam_id, student_id=current_user.id).first()
    if not sub:
        return "未提交", 404
    exam = db.session.get(Exam, exam_id)
    questions = json.loads(exam.questions_json)
    answers = json.loads(sub.answers_json)
    grading = json.loads(sub.grading_json or "{}")
    return render_template("student/result.html", exam=exam, sub=sub,
                           questions=questions, answers=answers, grading=grading, zip=zip)


# ── Teacher: Exam Results ───────────────────────────────

@app.route("/teacher/exam/<int:exam_id>/results")
@login_required
def exam_results(exam_id):
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    exam = db.session.get(Exam, exam_id)
    if not exam or exam.teacher_id != current_user.id:
        return "试卷不存在", 404
    subs = (Submission.query.filter_by(exam_id=exam_id)
            .order_by(Submission.submitted_at.desc()).all())
    return render_template("teacher/exam_results.html", exam=exam, subs=subs)


# ── Teacher: Grading (阅卷管理) ─────────────────────────

@app.route("/teacher/exam/<int:exam_id>/grade")
@login_required
def grade_list(exam_id):
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    exam = db.session.get(Exam, exam_id)
    if not exam or exam.teacher_id != current_user.id:
        return "试卷不存在", 404
    subs = (Submission.query.filter_by(exam_id=exam_id)
            .order_by(Submission.submitted_at.desc()).all())
    return render_template("teacher/grade_list.html", exam=exam, subs=subs)


@app.route("/teacher/exam/<int:exam_id>/grade/<int:sub_id>", methods=["GET", "POST"])
@login_required
def grade_detail(exam_id, sub_id):
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    exam = db.session.get(Exam, exam_id)
    sub = db.session.get(Submission, sub_id)
    if not exam or exam.teacher_id != current_user.id or not sub or sub.exam_id != exam_id:
        return "记录不存在", 404

    questions = json.loads(exam.questions_json)
    answers = json.loads(sub.answers_json)
    grading = json.loads(sub.grading_json or "{}")

    if request.method == "POST":
        per_q = 100 // len(questions) if questions else 0
        for i, q in enumerate(questions):
            if q.get("type") != "subjective":
                continue
            manual_score = request.form.get(f"manual_score_{i}", "").strip()
            manual_reason = request.form.get(f"manual_reason_{i}", "").strip()
            g = grading.setdefault(str(i), {})
            if manual_score:
                score = max(0, min(per_q, int(manual_score)))
                g["manual_score"] = score
                g["manual_reason"] = manual_reason
            else:
                g.pop("manual_score", None)
                g.pop("manual_reason", None)
        sub.grading_json = json.dumps(grading, ensure_ascii=False)
        sub.score = compute_score(questions, answers, grading)
        db.session.commit()
        return redirect(f"/teacher/exam/{exam_id}/grade")

    per_q = 100 // len(questions) if questions else 0
    return render_template("teacher/grade_detail.html", exam=exam, sub=sub,
                           questions=questions, answers=answers, grading=grading, per_q=per_q)


# ── Class Management (Teacher) ─────────────────────────

@app.route("/teacher/classes")
@login_required
def teacher_classes():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    classes = (SchoolClass.query.filter_by(teacher_id=current_user.id)
               .order_by(SchoolClass.created_at.desc()).all())
    class_info = [(c, c.students.count()) for c in classes]
    return render_template("teacher/classes.html", classes=class_info)


@app.route("/teacher/classes/create", methods=["POST"])
@login_required
def create_class():
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if not name:
        return redirect("/teacher/classes")
    cls = SchoolClass(name=name, description=description, teacher_id=current_user.id,
                      invite_code=generate_invite_code())
    db.session.add(cls)
    db.session.commit()
    return redirect("/teacher/classes")


@app.route("/teacher/classes/<int:class_id>")
@login_required
def class_detail(class_id):
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    cls = SchoolClass.query.filter_by(id=class_id, teacher_id=current_user.id).first()
    if not cls:
        return "班级不存在", 404
    students = cls.students.order_by(User.id).all()
    student_rows = []
    for st in students:
        subs = (Submission.query.filter_by(student_id=st.id)
                .order_by(Submission.submitted_at.desc()).all())
        student_rows.append((st, subs))
    return render_template("teacher/class_detail.html", cls=cls, student_rows=student_rows)


@app.route("/teacher/classes/<int:class_id>/delete", methods=["POST"])
@login_required
def delete_class(class_id):
    if current_user.role != "teacher":
        return redirect("/student/dashboard")
    cls = SchoolClass.query.filter_by(id=class_id, teacher_id=current_user.id).first()
    if cls:
        db.session.execute(class_student.delete().where(class_student.c.class_id == class_id))
        db.session.execute(class_exam.delete().where(class_exam.c.class_id == class_id))
        db.session.delete(cls)
        db.session.commit()
    return redirect("/teacher/classes")


# ── Student: Join Class ────────────────────────────────

@app.route("/student/join_class", methods=["GET", "POST"])
@login_required
def join_class():
    error = None
    success = None
    if request.method == "POST":
        code = request.form.get("invite_code", "").strip().upper()
        cls = SchoolClass.query.filter_by(invite_code=code).first()
        if not cls:
            error = "邀请码无效，请核对后重试"
        else:
            exists = db.session.query(class_student).filter_by(
                class_id=cls.id, student_id=current_user.id).first()
            if exists:
                error = "你已加入该班级"
            else:
                db.session.execute(class_student.insert().values(
                    class_id=cls.id, student_id=current_user.id))
                db.session.commit()
                success = f"成功加入班级「{cls.name}」"

    my_ids = [r[0] for r in db.session.execute(
        db.select(class_student.c.class_id).where(class_student.c.student_id == current_user.id)
    ).fetchall()]
    my_classes = SchoolClass.query.filter(SchoolClass.id.in_(my_ids)).all() if my_ids else []
    return render_template("student/join_class.html", error=error, success=success,
                           my_classes=my_classes)


def run_migrations():
    """Add missing columns to existing SQLite tables (create_all only adds new tables)."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)

    def has_column(table, column):
        return column in {c["name"] for c in inspector.get_columns(table)}

    def add_column(table, column, column_type):
        if not has_column(table, column):
            db.session.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {column_type}'))

    # Feature 1: User profile
    add_column("users", "email", "VARCHAR(128)")
    add_column("users", "real_name", "VARCHAR(128)")
    add_column("users", "created_at", "DATETIME")

    # Feature 2: Exam time settings
    add_column("exams", "start_time", "DATETIME")
    add_column("exams", "end_time", "DATETIME")
    add_column("exams", "duration_minutes", "INTEGER")

    # Feature 4: AI grading
    add_column("submissions", "grading_json", "TEXT")
    db.session.commit()


if __name__ == "__main__":
    os.makedirs(os.path.join(basedir, "instance"), exist_ok=True)
    with app.app_context():
        db.create_all()
        run_migrations()
    app.run(debug=True)
