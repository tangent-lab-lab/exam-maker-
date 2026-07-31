# Exam-Maker 系统设计文档

**日期**: 2026-07-31  
**状态**: 已确认

---

## 概述

Exam-Maker 是一个完整的在线考试系统，包含题库管理、AI 智能组卷、在线考试、阅卷评分和成绩分析。前后端分离架构，Docker 化部署，面向学校/机构内部使用。

---

## 一、技术栈

### 前端
- **Vue 3**（Composition API + `<script setup>`）— 渐进式前端框架
- **Vite** — 构建工具，开发热更新、生产打包
- **Pinia** — 状态管理（用户信息、权限、全局配置）
- **Vue Router** — 前端路由（基于角色的动态路由）
- **TDesign Vue Next** — 腾讯开源企业级 UI 组件库（表单/表格/弹窗/导航/图表等即开即用）
- **Axios** — HTTP 客户端，与后端 FastAPI 通信

### 后端
- **FastAPI** — 异步 Python Web 框架，自动生成 Swagger 文档
- **SQLAlchemy 2** — ORM（async 模式，配合 `aiosqlite`/`asyncpg`）
- **Alembic** — 数据库迁移工具
- **JWT**（`python-jose`）— 用户认证与鉴权
- **httpx** — 异步 HTTP 客户端，调用 AI API

### AI 能力
- **OpenAI 兼容协议** — 用 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL` 环境变量配置
- 默认模型：`deepseek-chat`，可切换为任何兼容接口（OpenAI、DeepSeek、Claude API via 兼容层等）

### 数据库
- **SQLite**（开发/小规模）— 零配置起步，`aiosqlite` 异步驱动
- **PostgreSQL**（生产/大规模）— 通过环境变量 `DATABASE_URL` 切换

### 交付与部署
- **Docker** — 前端 Nginx 静态服务 + 后端 Uvicorn，`docker-compose` 一键启动
- **GitHub Actions** — CI/CD：lint → test → build image → deploy

---

## 二、项目结构

```
exam_maker/
├── docker-compose.yml            # 一键启动
├── .github/workflows/
│   └── ci.yml                    # GitHub Actions CI/CD
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── main.py               # FastAPI 入口
│   │   ├── config.py             # 配置（环境变量读取）
│   │   ├── database.py           # 数据库引擎 & session
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── question.py
│   │   │   ├── exam.py
│   │   │   └── class_.py
│   │   ├── schemas/
│   │   │   ├── user.py           # Pydantic 请求/响应模型
│   │   │   ├── question.py
│   │   │   ├── exam.py
│   │   │   └── class_.py
│   │   ├── routers/
│   │   │   ├── auth.py           # 登录/注册/Token
│   │   │   ├── admin.py          # 超级管理员接口
│   │   │   ├── teacher.py        # 老师接口
│   │   │   └── student.py        # 学生接口
│   │   ├── services/
│   │   │   ├── question_bank.py
│   │   │   ├── exam_builder.py
│   │   │   ├── grading.py
│   │   │   └── ai_client.py      # OpenAI 兼容协议封装
│   │   └── utils/
│   │       ├── security.py       # JWT + 密码哈希
│   │       └── permissions.py    # 角色权限依赖注入
│   └── tests/
│
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.ts               # Vue 入口
│       ├── App.vue
│       ├── router/
│       │   └── index.ts          # 路由配置（角色守卫）
│       ├── stores/
│       │   ├── auth.ts           # 用户 & Token
│       │   └── settings.ts       # 全局设置
│       ├── api/
│       │   ├── client.ts         # Axios 实例 + 拦截器
│       │   └── *.ts              # 各模块 API 调用
│       ├── views/
│       │   ├── admin/
│       │   ├── teacher/
│       │   └── student/
│       ├── components/
│       │   ├── layout/
│       │   │   ├── AppLayout.vue   # 侧边栏+内容区骨架
│       │   │   ├── Sidebar.vue
│       │   │   └── Topbar.vue
│       │   └── common/             # 可复用组件
│       └── styles/
│           └── variables.css
│
└── uploads/                        # 文件上传题存储（挂载卷）
```

---

## 三、用户角色与权限

三种角色按层级授权：

| 能力 | 超级管理员 | 老师 | 学生 |
|------|:---:|:---:|:---:|
| 管理用户（创建/禁用/删除） | ✓ | | |
| 创建/管理班级 | ✓ | ✓ | |
| 题库管理（增删改查） | ✓ | ✓ | |
| AI 智能出题 | ✓ | ✓ | |
| 手动组卷 | ✓ | ✓ | |
| 发布考试/练习/作业 | ✓ | ✓ | |
| 批改主观题 | ✓ | ✓ | |
| 查看成绩统计 | ✓ | ✓ | |
| 参加考试/练习/作业 | | | ✓ |
| 查看自己的成绩 | | | ✓ |
| 查看题目解析（练习模式） | | | ✓ |

- 超级管理员拥有一切权限，可查看全局数据统计
- 老师只能管理自己创建的班级、题库、试卷
- 学生只能访问被分配的考试和自己的成绩
- 注册采用邀请制：管理员创建老师账号，老师创建学生账号或生成班级邀请码

---

## 四、题库模块

### 数据模型

```
Question
├── id              (主键)
├── teacher_id      (所属老师，外键)
├── type            (枚举: 单选/多选/判断/填空/简答/编程/文件上传/匹配)
├── content         (题干，支持富文本/LaTeX)
├── options         (JSON — 选择题/匹配题的选项)
├── answer          (JSON — 正确答案，不同题型结构不同)
├── explanation     (解析，可选)
├── difficulty      (1-5 难度等级)
├── tags            (字符串标签，逗号分隔)
├── score_default   (默认分值)
├── is_public       (是否公开给其他老师)
├── created_at
└── updated_at
```

### 功能
- 手工录入/编辑/删除题目
- 批量导入（CSV/Excel 模板）
- 按题型、难度、标签筛选和搜索
- AI 生成题目 — 输入主题/知识点/数量/难度，AI 生成后老师确认入库
- 题目公开/复用机制

---

## 五、试卷与组卷模块

### 数据模型

```
Exam
├── id                  (主键)
├── teacher_id          (外键)
├── title               (试卷名称)
├── description         (考试说明)
├── mode                (枚举: 正式考试 / 练习 / 作业)
├── status              (枚举: 草稿 / 已发布 / 已关闭)
├── duration_minutes    (考试限时，练习模式可为 0=不限时)
├── start_time          (开始时间)
├── end_time            (截止时间)
├── allow_late          (作业模式是否允许补交)
├── max_attempts        (最大作答次数，考试固定为 1)
├── shuffle_questions   (是否乱序出题)
├── show_score          (交卷后是否立即显示成绩)
├── show_explanation    (是否显示解析)
├── total_score         (总分，自动计算)
├── created_at
└── updated_at

ExamQuestion (中间表)
├── exam_id
├── question_id
├── sort_order          (题号排序)
└── score               (每题分值，可覆盖默认值)
```

### 组卷方式
1. **手动组卷** — 筛选题目 → 逐个加入试卷 → 拖拽排序 → 设定分值。Vue 组件内完成交互。
2. **AI 智能组卷** — 输入考点范围、题型分布、难度比例、总分值，AI 从题库中匹配合适题目组合。

### 其他功能
- 试卷预览、复制、导出 PDF

---

## 六、在线考试与阅卷

### 考试流程

```
开始考试 → 答题页(计时器) → 提交 → 客观题自动判分 → 等待主观题批改 → 查看成绩
```

### 考试页面布局
- 左侧题目导航（题号列表 + 已答/未答/标记状态）
- 右侧当前题目
- 顶部倒计时器，时间到自动交卷

### 三种考试模式

| 模式 | 限时 | 次数 | 解析 | 特色 |
|------|:--:|:--:|:--:|------|
| 正式考试 | ✓ | 1次 | 可选 | 交卷即锁定 |
| 练习 | 不限 | N次 | 默认显示 | 每次提交即时出分和解析 |
| 作业 | ✓ | 1次 | 可选 | 有截止时间，可设置允许补交 |

### 防作弊
- 切标签页次数记录，超出阈值可自动交卷（老师可配置）

### 阅卷
- **客观题**（单选/多选/判断/填空/匹配）：交卷后即时自动判分
- **主观题**（简答/编程/文件上传）：老师在答卷列表里逐题手动打分
- **AI 辅助批改**（可选）：AI 对主观题给出评分建议和评语，老师确认或调整

### 成绩管理
- 按考试/班级查看成绩分布（平均分、最高最低、各题正确率）
- 导出成绩报表（CSV）
- 学生端查看自己的成绩单和错题集

---

## 七、班级管理模块

```
Class
├── id            (主键)
├── teacher_id    (外键)
├── name          (班级名称)
├── invite_code   (邀请码，6位字母数字)
├── description
├── created_at

ClassMember (中间表)
├── class_id
├── student_id
├── joined_at
```

- 老师创建班级 → 自动生成邀请码
- 学生输入邀请码加入班级
- 老师可移除学生、批量导入学生列表
- 发布考试时选择目标班级（一个或多个）
- 管理员可见所有班级，老师仅见自己的

---

## 八、AI 模块（OpenAI 兼容协议）

封装统一服务 `AIClient`，所有 AI 调用走同一入口。通过环境变量配置，遵循 OpenAI Chat Completions 协议：

```
# .env 示例
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-xxxxxxxx
OPENAI_MODEL=deepseek-chat
```

可切换为任意兼容接口：DeepSeek、OpenAI、Claude API（via 兼容层）、本地模型（vLLM/ollama）等。

| 功能 | 触发位置 | AI 做什么 |
|------|---------|---------|
| 生成题目 | 题库页 "AI 出题" | 根据知识点/题型/难度/数量生成题目 JSON |
| 智能组卷 | 组卷页 "AI 组卷" | 从题库按约束条件挑选题目组合 |
| 辅助批改 | 阅卷页 "AI 评分" | 对主观题答案给出评分建议和简评 |
| 生成解析 | 题库页题目旁 | 为题目生成解题思路和知识点评析 |

- 后端通过 `httpx` + `asyncio` 异步调用 AI API，不阻塞请求
- 全局管理员可覆盖环境变量中的 API Key 和 Base URL
- AI 生成结果先返回前端展示确认，确认后写入数据库
- 超时 60 秒，失败返回友好错误信息

---

## 九、UI 布局

基于 TDesign 组件库的管理后台布局：

```
┌──────────────┬──────────────────────────────────────┐
│   Logo       │  面包屑导航  │  通知  │  用户头像 ▼    │
│   ────────   ├──────────────────────────────────────┤
│   📊 仪表盘    │                                       │
│   📚 题库     │                                       │
│   📝 试卷管理 │           <router-view />              │
│   👥 班级管理 │          主内容区域                     │
│   📈 成绩统计 │                                       │
│   🤖 AI助手   │                                       │
│   ────────   │                                       │
│   ⚙ 系统设置  │                                       │
└──────────────┴──────────────────────────────────────┘
```

- **布局骨架**：`AppLayout.vue` 使用 TDesign `Layout` + `Aside` + `Content` 组件，侧边栏 232px 可折叠
- **侧边栏**：`t-menu` 根据角色（admin/teacher/student）动态渲染菜单项，图标使用 TDesign Icons
- **顶部栏**：面包屑 + 通知图标 + 用户下拉菜单
- **内容区**：`<router-view />` 承载所有页面级组件，每个页面是一个独立路由
- **组件选用**：表格用 `t-table`、表单用 `t-form`、弹窗用 `t-dialog`、选择器用 `t-select` 等
- **配色**：TDesign 默认主题色（蓝色系），支持暗色模式切换
- **响应式**：侧边栏在小屏自动折叠为触发式导航（TDesign `t-drawer`）

---

## 十、非功能性需求

### 安全性
- **密码**：`bcrypt`（passlib）哈希存储
- **认证**：JWT access token + refresh token，token 过期后自动续签或跳转登录
- **鉴权**：FastAPI 依赖注入 `Depends(get_current_user)` + 角色分级 `Depends(require_role(...))`
- **防注入**：SQLAlchemy 2 参数化查询；Pydantic 请求体校验
- **CSRF**：前后端分离架构下，JWT 存 httpOnly cookie + `SameSite=Lax`

### 性能
- SQLite + `aiosqlite` 在单机小并发场景满足需求
- 生产切换 PostgreSQL：修改 `DATABASE_URL` 环境变量 + `asyncpg` 驱动，代码无需改动
- 前端 Vite code-splitting 按路由懒加载，首屏体积可控

### 可扩展性
- 前后端独立部署，可分别水平扩展
- 数据库驱动抽象在 `database.py`，SQLite → PostgreSQL 仅改连接串
- AI 提供商可随时通过环境变量切换，无需改业务代码

### 可用性
- `docker-compose up` 一键启动（包含前端 Nginx、后端 Uvicorn、可选 PostgreSQL）
- 后端自动生成 Swagger 文档（`/docs`），前后端联调可直接在浏览器测试 API
- GitHub Actions 自动 lint + test + build，推送镜像至 registry
