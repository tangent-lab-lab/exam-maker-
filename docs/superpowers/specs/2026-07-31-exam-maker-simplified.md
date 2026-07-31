# Exam-Maker 简化版设计文档

**日期**: 2026-07-31
**状态**: 已确认

---

## 概述

一个最简可用的在线考试系统：教师通过 AI 出卷，学生在线答题，系统自动阅卷并显示成绩。

---

## 一、技术栈

| 层 | 选型 |
|----|------|
| 后端 | Python 3 + Flask，所有路由写在单个 `app.py` 中 |
| 数据库 | SQLite，通过 Flask-SQLAlchemy ORM 操作 |
| 前端 | Flask 内置 Jinja2 模板 + Bootstrap 5 CDN |
| 认证 | Flask-Login，session 管理登录状态 |
| AI | OpenAI 兼容协议，通过 `.env` 配置 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`，默认 DeepSeek |

---

## 二、项目文件结构

```
exam_maker/
├── .env                          # LLM 配置（不入 git）
├── requirements.txt              # flask, flask-sqlalchemy, flask-login, httpx, python-dotenv
├── app.py                        # Flask 应用（所有路由 + 模型 + AI 调用）
├── instance/
│   └── exam_maker.db             # SQLite 数据库文件
├── templates/
│   ├── base.html                 # Bootstrap 骨架（导航栏）
│   ├── login.html                # 登录页
│   ├── register.html             # 注册页（选择角色：教师/学生）
│   ├── teacher/
│   │   ├── dashboard.html        # 教师仪表盘
│   │   ├── create_exam.html      # AI 出卷表单页
│   │   └── exam_results.html     # 某试卷的学生成绩列表
│   └── student/
│       ├── dashboard.html        # 学生仪表盘（试卷列表）
│       ├── take_exam.html        # 答题页
│       └── result.html           # 成绩页
└── static/
    └── style.css                 # 少量自定义样式
```

---

## 三、数据模型（3 张表）

### User
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| username | String(64), unique | |
| password_hash | String(128) | Flask-Login 验证 |
| role | String(16) | `teacher` 或 `student` |

### Exam
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| teacher_id | FK → User | 出卷教师 |
| title | String(256) | 试卷名称 |
| questions_json | Text (JSON) | 存储完整试卷题目列表（含题型、题干、选项、答案、分值） |
| status | String(16) | `draft` / `published`，只有 published 的试卷学生可见 |
| created_at | DateTime | |

### Submission
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| exam_id | FK → Exam | |
| student_id | FK → User | |
| answers_json | Text (JSON) | 学生作答 `{"0":"A","1":"openai"}` |
| score | Integer | 自动阅卷得分 |
| submitted_at | DateTime | |

---

## 四、功能清单

### 1. 用户注册/登录
- 注册页：填写用户名、密码、选择角色（教师/学生），注册后自动登录。
- 登录页：输入用户名密码，登录后按角色跳转到对应仪表盘。
- 登出：清除 session 回到登录页。

### 2. 教师 AI 出卷
- 出卷表单：输入试卷标题 + 题目数量 + 难度(1-5) + 题型勾选（单选/多选/填空）。
- 点击"生成试卷"→ 后端调用 DeepSeek API，要求返回 JSON 格式的题目列表。
- AI 返回的 JSON 存入 `Exam.questions_json`，试卷状态为 `published`。
- 生成完成后跳转到教师仪表盘，显示已创建的试卷列表，每份试卷可查看学生成绩。

### 3. 学生答题
- 学生仪表盘列出所有 `published` 状态的试卷。
- 点击试卷进入答题页：每道题渲染对应表单控件（单选→radio、多选→checkbox、填空→input）。
- 点"交卷"→ 答案存入 `Submission.answers_json`。

### 4. 自动阅卷
- 交卷时后端逐一比对：学生答案 vs `Exam.questions_json` 中每题的正确答案。
- 客观题（单选/多选/填空）自动判分，每题分值 = 100 / 总题数，总分存入 `Submission.score`。
- 学生端成绩页显示分数和每道题的正确答案对照。

---

## 五、AI 出卷提示词逻辑

后端构造如下 prompt 发给 DeepSeek：

```
你是一个出题助手。请生成{数量}道题目，难度{1-5}，题型包含{单选,多选,填空}。
每题包含：type(题型), question(题干), options(选项列表,非选择题为空数组), answer(正确答案), score(分值=100/总量取整)。
只返回 JSON 数组，不要任何其他内容。
```

后端解析返回的 JSON 数组，存入 `Exam.questions_json`。

---

## 六、路由设计

```
GET  /                      → 重定向到登录页
GET  /auth/login            → 登录页
POST /auth/login            → 处理登录
GET  /auth/register         → 注册页
POST /auth/register         → 处理注册
GET  /auth/logout           → 登出

GET  /teacher/dashboard     → 教师仪表盘（试卷列表）
GET  /teacher/create_exam   → AI 出卷表单页
POST /teacher/create_exam   → 调用 AI 生成试卷
GET  /teacher/exam/<id>/results → 查看某试卷成绩

GET  /student/dashboard     → 学生仪表盘（可答试卷列表）
GET  /student/exam/<id>     → 答题页
POST /student/exam/<id>/submit → 提交答案
GET  /student/exam/<id>/result  → 查看成绩
```

---

## 七、页面速写

### base.html — Bootstrap 导航栏 + `{% block content %}`

### login.html / register.html — 居中卡片表单，注册页多一个角色下拉框。

### teacher/create_exam.html — 表单：标题 input + 数量 select(5/10/15/20) + 难度 radio(1-5) + 题型 checkbox。点"生成"→ loading 提示 → 跳转回仪表盘。

### student/take_exam.html — 题目列表渲染，每题一行。底部"交卷"按钮。

### student/result.html — 总分大字显示 + 题目列表（每题的正确答案 vs 你的答案，正确绿色错误红色）。

---

## 八、验收标准

1. 打开应用 → 看到登录页 → 注册一个教师账号 → 注册成功自动跳转教师仪表盘。
2. 教师仪表盘点"创建试卷" → 填参数(数量=5, 难度=3, 题型=单选/多选) → 点生成 → 等待 5-15 秒 → 回到仪表盘看到新试卷。
3. 新开浏览器 → 注册一个学生账号 → 仪表盘看到刚才教师生成的试卷。
4. 点击试卷 → 进入答题页 → 选择/填写答案 → 交卷 → 跳转成绩页显示分数和答案对照。
5. 客观题分数完全正确（学生答案与正确答案严格匹配计分）。
