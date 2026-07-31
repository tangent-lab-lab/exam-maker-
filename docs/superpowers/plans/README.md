# Exam-Maker 计划索引

> 共 12 个 Plan，按依赖顺序排列。每个 Plan 改动 ≤ 30 行代码，可独立完成和验证。

---

| # | Plan | 内容 | 创建/修改 | 依赖 |
|---|------|------|-----------|------|
| 001 | [项目骨架](./001-project-skeleton.md) | requirements.txt + .env + app.py 入口 + base.html | 5 个新文件 | 无 |
| 002 | [User 模型+登录集成](./002-user-model-login.md) | User 模型 + Flask-Login user_loader | 修改 app.py | 001 |
| 003 | [注册+登录路由+模板](./003-auth-routes-templates.md) | auth 路由 + login.html + register.html | 修改 app.py + 2 个新模板 | 002 |
| 004 | [Exam 模型](./004-exam-model.md) | Exam 模型（questions_json 存 JSON） | 修改 app.py | 002 |
| 005 | [教师仪表盘](./005-teacher-dashboard.md) | 试卷列表 + dashboard.html | 修改 app.py + 1 个新模板 | 003, 004 |
| 006 | [AI 客户端+出卷 POST](./006-ai-client-create-exam.md) | call_llm 函数 + POST 出卷路由（解析 AI 返回 JSON 存入 DB） | 修改 app.py | 004, 005 |
| 007 | [出卷表单页](./007-create-exam-form.md) | GET 出卷页 + create_exam.html（表单：标题/数量/难度/题型） | 修改 app.py + 1 个新模板 | 006 |
| 008 | [学生仪表盘](./008-student-dashboard.md) | 学生端试卷列表 + dashboard.html | 修改 app.py + 1 个新模板 | 003, 004 |
| 009 | [答题页](./009-take-exam-page.md) | GET 答题页 + take_exam.html（渲染单选/多选/填空） | 修改 app.py + 1 个新模板 | 008 |
| 010 | [提交+自动阅卷](./010-submit-and-grade.md) | Submission 模型 + POST 提交路由（含逐题比对判分） | 修改 app.py | 009 |
| 011 | [成绩页](./011-exam-result-page.md) | 学生端成绩页 + result.html（分数 + 答案对照） | 修改 app.py + 1 个新模板 | 010 |
| 012 | [教师成绩查看](./012-teacher-exam-results.md) | 教师端学生成绩列表 + exam_results.html | 修改 app.py + 1 个新模板 | 010 |

---

## Spec 覆盖率

| Spec 章节 | 覆盖 Plan |
|-----------|-----------|
| 三、数据模型（3 张表） | 002 User / 004 Exam / 010 Submission |
| 四-1. 用户注册/登录 | 003 |
| 四-2. 教师 AI 出卷 | 005 仪表盘 / 006 AI 调用 / 007 表单页 / 012 成绩查看 |
| 四-3. 学生答题 | 008 试卷列表 / 009 答题页 |
| 四-4. 自动阅卷 | 010 判分逻辑 / 011 成绩页 |
| 五、AI 提示词逻辑 | 006 |
| 六、路由设计（11 条路由） | 003 (5条) / 005 (1条) / 006 (1条) / 007 (1条) / 008 (1条) / 009 (1条) / 010 (1条) / 011 (1条) / 012 (1条) |

---

## 使用方式

1. 从 001 开始，按序号顺序执行
2. 每个 Plan 完成后**立即验证**其验收标准 → 通过再进入下一个
3. Plan 共用一个 `app.py`，后续 Plan 在已有代码上**追加**（不要覆盖）
4. 全部 12 个 Plan 完成后，对照 Spec 第八节验收标准做端到端测试
