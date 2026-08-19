# Exam-Maker 简化版设计文档

**日期**: 2026-07-31（更新于 2026-08-05）
**状态**: 已确认

---

## 概述

一个最简可用的在线考试系统：教师通过 **AI 出卷**、**手动上传试卷** 或 **按难度配比从题库抽题** 三种方式之一出卷，学生在线答题，系统自动阅卷并显示成绩。

---

## 一、技术栈

| 层 | 选型 |
|----|------|
| 后端 | Python 3 + Flask，所有路由写在单个 `app.py` 中 |
| 数据库 | SQLite，通过 Flask-SQLAlchemy ORM 操作 |
| 前端 | Flask 内置 Jinja2 模板 + Bootstrap 5 CDN |
| 认证 | Flask-Login，session 管理登录状态 |
| AI | OpenAI 兼容协议，通过 `.env` 配置 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`，默认 DeepSeek |
| 文件解析 | `python-docx`（Word）、`PyPDF2`（PDF）、内置 `open()`（TXT）；提取文本后统一由 LLM 结构化 |

---

## 二、项目文件结构

```
exam_maker/
├── .env                          # LLM 配置（不入 git）
├── requirements.txt              # flask, flask-sqlalchemy, flask-login, httpx, python-dotenv, python-docx, PyPDF2
├── app.py                        # Flask 应用（所有路由 + 模型 + AI 调用）
├── instance/
│   └── exam_maker.db             # SQLite 数据库文件
├── templates/
│   ├── base.html                 # Bootstrap 骨架（导航栏）
│   ├── login.html                # 登录页
│   ├── register.html             # 注册页（选择角色：教师/学生）
│   ├── teacher/
│   │   ├── dashboard.html        # 教师仪表盘（试卷列表 + 题库入口）
│   │   ├── create_exam.html      # 出卷方式选择页
│   │   ├── create_exam_ai.html   # AI 出卷表单页
│   │   ├── create_exam_upload.html   # 手动上传出卷页
│   │   ├── create_exam_ratio.html    # 难度配比出卷页
│   │   ├── question_bank.html    # 题库管理页
│   │   ├── knowledge_points.html # 知识点管理页
│   │   └── exam_results.html     # 某试卷的学生成绩列表
│   └── student/
│       ├── dashboard.html        # 学生仪表盘（试卷列表）
│       ├── take_exam.html        # 答题页
│       └── result.html           # 成绩页
└── static/
    └── style.css                 # 少量自定义样式
```

---

## 三、数据模型（6 张表）

### User（不变）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| username | String(64), unique | |
| password_hash | String(128) | Flask-Login 验证 |
| role | String(16) | `teacher` 或 `student` |

### KnowledgePoint（新增 — 知识点）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| name | String(128), unique | 知识点名称，如"一元二次方程" |
| teacher_id | FK → User | 创建者（教师） |

> 知识点由教师自行创建和管理，属于教师私有数据。

### Question（新增 — 题库）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| teacher_id | FK → User | 题目所属教师 |
| type | String(16) | `single_choice` / `multi_choice` / `fill_blank` |
| question_text | Text | 题干 |
| options_json | Text (JSON) | 选项列表，填空题为空数组 `[]` |
| answer | String(256) | 正确答案 |
| difficulty | Integer | 难度 1-5 |
| source | String(16) | `ai_generate` / `manual_upload` |
| created_at | DateTime | |

### question_knowledge_points（新增 — 题目-知识点关联表）
| 字段 | 类型 | 说明 |
|------|------|------|
| question_id | FK → Question | |
| knowledge_point_id | FK → KnowledgePoint | |

> 联合主键 `(question_id, knowledge_point_id)`，一个题目可关联多个知识点。

### Exam（更新）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | |
| teacher_id | FK → User | 出卷教师 |
| title | String(256) | 试卷名称 |
| creation_mode | String(16) | **新增**：`ai_generate` / `manual_upload` / `difficulty_ratio` |
| questions_json | Text (JSON) | 存储完整试卷题目列表（含题型、题干、选项、答案、分值） |
| status | String(16) | `draft` / `published`，只有 published 的试卷学生可见 |
| created_at | DateTime | |

### Submission（不变）
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

### 2. 教师出卷 — 三种方式并列

教师进入出卷页首先看到出卷方式选择：AI 出卷 / 手动上传 / 难度配比。

#### 2a. AI 出卷（已有）
- 出卷表单：输入试卷标题 + 题目数量 + 难度(1-5) + 题型勾选（单选/多选/填空）。
- 点击"生成试卷"→ 后端调用 DeepSeek API，要求返回 JSON 格式的题目列表。
- AI 返回的 JSON 存入 `Exam.questions_json`，试卷状态为 `published`，`creation_mode = 'ai_generate'`。
- **可选**：勾选"同时存入题库"复选框，将生成的题目一并写入 `Question` 表，供后续难度配比出卷复用。

#### 2b. 手动上传试卷（新增）
- 上传表单：输入试卷标题 + 选择文件（支持 `.docx` / `.pdf` / `.txt`）+ 选择或新建知识点标签（可选）。
- 后端流程：
  1. 根据文件扩展名选择解析器提取原始文本。
  2. 将提取的文本发给 LLM，要求返回结构化 JSON 题目数组（格式同 AI 出卷）。
  3. 每道题附加解析出的 `difficulty` 字段（LLM 自动判断 1-5）。
- 解析完成后进入**预览确认页**：教师可逐题检查、修改、删除，确认无误后保存。
- 所有题目存入 `Question` 表（`source = 'manual_upload'`），同时根据所选题目组装 `Exam.questions_json` 并发布试卷，`creation_mode = 'manual_upload'`。
- 若教师在预览页取消，题目不保存，试卷不创建。

#### 2c. 按难度配比出卷（新增）
- 抽题表单：输入试卷标题 + 总题数 + 题型勾选 + 难度比例输入（如 `3:5:2` 对应 简单:中等:困难 各 30%/50%/20%）+ 可选知识点筛选。
- 后端流程：
  1. 根据比例计算各难度所需题数（如 20 题 × 3:5:2 → 简单 6 题、中等 10 题、困难 4 题）。
  2. 从当前教师的 `Question` 表中按条件筛选，各难度随机抽取所需数量。
  3. 若某难度题目不足，提示教师调整比例或先补充题库。
- 抽取的题目组成 `Exam.questions_json`，试卷发布，`creation_mode = 'difficulty_ratio'`。
- 抽题逻辑使用 SQL `ORDER BY RANDOM() LIMIT n`，保证随机性。

### 3. 知识点管理（新增）
- 教师可在知识点管理页创建、编辑、删除知识点（CRUD）。
- 每个知识点属于创建它的教师，教师之间知识点隔离。
- 在题库管理页可为每道题勾选关联的知识点（多对多）。
- 出卷时可按知识点筛选题目范围（适用于难度配比出卷和手动选题）。

### 4. 题库管理（新增）
- 教师可在题库管理页查看自己库中的所有题目，支持按知识点、难度、题型筛选。
- 支持逐题编辑（修改题干、选项、答案、难度、知识点关联）和删除。
- 题目来源标记（`ai_generate` / `manual_upload`）只读展示。

### 5. 学生答题（不变）
- 学生仪表盘列出所有 `published` 状态的试卷。
- 点击试卷进入答题页：每道题渲染对应表单控件（单选→radio、多选→checkbox、填空→input）。
- 点"交卷"→ 答案存入 `Submission.answers_json`。

### 6. 自动阅卷（不变）
- 交卷时后端逐一比对：学生答案 vs `Exam.questions_json` 中每题的正确答案。
- 客观题（单选/多选/填空）自动判分，每题分值 = 100 / 总题数，总分存入 `Submission.score`。
- 学生端成绩页显示分数和每道题的正确答案对照。

---

## 五、AI 提示词逻辑

### 5a. AI 出卷提示词（已有）

后端构造如下 prompt 发给 LLM：

```
你是一个出题助手。请生成{数量}道题目，难度{1-5}，题型包含{单选,多选,填空}。
每题包含：type(题型), question(题干), options(选项列表,非选择题为空数组), answer(正确答案), difficulty(难度1-5)。
只返回 JSON 数组，不要任何其他内容。
```

后端解析返回的 JSON 数组，存入 `Exam.questions_json`（及可选的 `Question` 表）。

### 5b. 文件解析提示词（新增）

上传文件提取文本后，构造如下 prompt 发给 LLM：

```
你是一个试卷解析助手。以下是从上传文件中提取的文本内容，请将其中的题目结构化。
每道题包含：type(题型: single_choice/multi_choice/fill_blank), question(题干), options(选项列表,非选择题为空数组), answer(正确答案), difficulty(难度1-5,根据题目复杂度自行判断)。
只返回 JSON 数组，不要任何其他内容。

文本内容：
{extracted_text}
```

---

## 六、路由设计

```
# 认证
GET  /                      → 重定向到登录页
GET  /auth/login            → 登录页
POST /auth/login            → 处理登录
GET  /auth/register         → 注册页
POST /auth/register         → 处理注册
GET  /auth/logout           → 登出

# 教师 — 仪表盘 & 出卷
GET  /teacher/dashboard         → 教师仪表盘（试卷列表 + 题库统计）
GET  /teacher/create_exam       → 出卷方式选择页
GET  /teacher/create_exam/ai    → AI 出卷表单页
POST /teacher/create_exam/ai    → 调用 AI 生成试卷
GET  /teacher/create_exam/upload    → 手动上传出卷页
POST /teacher/create_exam/upload    → 上传文件 + 解析 → 重定向预览页
GET  /teacher/create_exam/upload/preview → 预览解析结果
POST /teacher/create_exam/upload/confirm → 确认保存并创建试卷
POST /teacher/create_exam/upload/cancel  → 取消，丢弃解析结果
GET  /teacher/create_exam/ratio     → 难度配比出卷页
POST /teacher/create_exam/ratio     → 按比例抽题并创建试卷
GET  /teacher/exam/<id>/results     → 查看某试卷成绩

# 教师 — 题库 & 知识点
GET  /teacher/question_bank            → 题库管理页（筛选 + 列表）
GET  /teacher/question/<id>/edit       → 编辑题目页
POST /teacher/question/<id>/edit       → 保存编辑
POST /teacher/question/<id>/delete     → 删除题目
GET  /teacher/knowledge_points         → 知识点管理页
POST /teacher/knowledge_points/create  → 创建知识点
POST /teacher/knowledge_points/<id>/edit   → 编辑知识点
POST /teacher/knowledge_points/<id>/delete → 删除知识点

# 学生
GET  /student/dashboard         → 学生仪表盘（可答试卷列表）
GET  /student/exam/<id>         → 答题页
POST /student/exam/<id>/submit  → 提交答案
GET  /student/exam/<id>/result  → 查看成绩
```

---

## 七、页面速写

### base.html — Bootstrap 导航栏 + `{% block content %}`

### login.html / register.html — 居中卡片表单，注册页多一个角色下拉框。

### teacher/create_exam.html — 出卷方式选择页：三张卡片（AI 出卷 / 手动上传 / 难度配比），点击进入对应流程。

### teacher/create_exam_ai.html — 表单：标题 input + 数量 select(5/10/15/20) + 难度 radio(1-5) + 题型 checkbox + "同时存入题库"复选框。点"生成"→ loading 提示 → 跳转回仪表盘。

### teacher/create_exam_upload.html — 表单：标题 input + 文件选择器（accept .docx/.pdf/.txt）+ 知识点多选（可选）。点"上传解析"→ loading → 跳转预览页。

### teacher/create_exam_upload_preview.html — 预览页：试卷标题 + 解析出的题目列表（每道题显示类型、题干、选项、答案、难度），支持逐题编辑和删除。底部"确认创建"和"取消"两个按钮。

### teacher/create_exam_ratio.html — 表单：标题 input + 总题数 + 题型 checkbox + 难度比例输入（三个数字 input，如 3:5:2）+ 知识点筛选（可选多选下拉）。点"生成试卷"→ 后端抽题 → 跳转仪表盘。若某难度题目不足，返回本页并显示提示。

### teacher/question_bank.html — 筛选栏（知识点下拉、难度、题型）+ 题目列表表格（题干截断显示、类型、难度、来源、关联知识点标签）+ 每行编辑/删除按钮。

### teacher/question_edit.html — 单题编辑表单：题型、题干、选项（动态添加/删除）、正确答案、难度、知识点勾选。

### teacher/knowledge_points.html — 知识点列表 + 新建输入框 + 每行编辑/删除按钮。

### student/take_exam.html — 题目列表渲染，每题一行。底部"交卷"按钮。

### student/result.html — 总分大字显示 + 题目列表（每题的正确答案 vs 你的答案，正确绿色错误红色）。

---

## 八、验收标准

### 已有功能
1. 打开应用 → 看到登录页 → 注册一个教师账号 → 注册成功自动跳转教师仪表盘。
2. 教师仪表盘点"创建试卷" → 选择"AI 出卷" → 填参数(数量=5, 难度=3, 题型=单选/多选) → 点生成 → 等待 5-15 秒 → 回到仪表盘看到新试卷。
3. 新开浏览器 → 注册一个学生账号 → 仪表盘看到刚才教师生成的试卷。
4. 点击试卷 → 进入答题页 → 选择/填写答案 → 交卷 → 跳转成绩页显示分数和答案对照。
5. 客观题分数完全正确（学生答案与正确答案严格匹配计分）。

### 新增功能
6. **知识点管理**：教师创建知识点"一元二次方程""勾股定理"，在题库中为题目关联知识点。
7. **手动上传出卷**：教师上传一个包含 10 道题的 `.docx` 文件 → 系统解析并在预览页展示结构化题目 → 教师确认后试卷创建成功，题目同时入库。
8. **难度配比出卷**：题库中有各难度题目总计 30 道以上 → 教师选择总题数 20，难度比例 3:5:2 → 系统正确按比例抽取（简单 6、中等 10、困难 4）→ 试卷创建成功。
9. **难度配比题目不足**：题库中困难题仅 2 道，但比例要求 4 道 → 系统提示"困难题不足，当前仅 2 道"。
10. **题库筛选**：教师可按知识点、难度、题型筛选题库题目，编辑或删除题目。
11. **AI 出卷可选入库**：勾选"同时存入题库"，AI 生成的题目同步写入 Question 表，后续可用于难度配比出卷。
12. 三种出卷方式创建的试卷，学生端均能正常答题和查看成绩，无功能差异。
