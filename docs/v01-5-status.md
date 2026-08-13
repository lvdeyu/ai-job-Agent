# V0.1-5 状态记录：模拟面试与 RAG 基础闭环

更新时间：2026-08-13

## 已完成

- 新增面试题库表 `question_bank_items`。
- 新增模拟面试会话表 `interview_sessions`。
- 新增模拟面试轮次表 `interview_turns`。
- 新增数据库迁移：
  - `backend/alembic/versions/20260813_0007_v01_interviews.py`
- 后端新增模拟面试 API：
  - `POST /api/v1/interviews`：从岗位池岗位开始模拟面试。
  - `GET /api/v1/interviews`：查询当前用户面试会话。
  - `GET /api/v1/interviews/{session_id}`：查看单个面试会话。
  - `POST /api/v1/interviews/{session_id}/answers`：提交回答并触发评分、追问、下一题或报告生成。
  - `POST /api/v1/interviews/{session_id}/finish`：用户主动结束并生成报告。
- 题库种子数据会在首次开始面试时从 `knowledge/interview_question_bank/seeds/*.jsonl` 自动导入数据库。
- 当前检索模式为 `pgvector-fallback-v1` / `local-keyword-v1`：
  - 题库种子导入时会生成 `local-hash-embedding-v1` 本地确定性 embedding。
  - 运行时优先按本地 embedding 相似度 + 关键词相关性排序。
  - 根据岗位标题、JD、标签、默认简历和最近一次岗位评测拆解结果构造上下文。
  - 按题库 `skill_tags` 和 `embedding_text` 做本地关键词召回与排序。
  - 保留后续替换为 `pgvector` 和真实 embedding 的接口边界。
- 当前评分模式为 `local-rubric-v1`：
  - 根据题库 `scoring_rubric`、参考答案、技能标签和用户回答做规则评分。
  - 回答偏弱时生成追问。
  - 达到主问题上限后由代码终止并生成报告，避免无限追问。
- 面试报告包含：
  - 总分。
  - 回答轮数。
  - 覆盖技能。
  - 总结。
  - 优势。
  - 缺口。
  - 复习建议。
  - 问题、回答、得分、rubric 证据和题库引用。
- 前端岗位池启用 `开始模拟面试`。
- 前端新增 `模拟面试` 工作台分区：
  - 展示当前问题。
  - 支持提交回答。
  - 展示追问或下一题。
  - 展示已回答轮次、分数、反馈和评分证据。
  - 支持主动结束并生成报告。
- 面试响应新增 `checkpoint` 快照：
  - 标识当前持久化恢复模式。
  - 返回当前待答轮次、已回答轮数和可恢复会话 ID。

## 当前实现边界

- 本阶段先跑通本地可演示闭环，没有接入真实 LLM 打分。
- 暂未接入真实外部 embedding API；当前使用本地确定性 embedding，适合本地闭环验收。
- 暂未把数据库列切换成 PostgreSQL `vector` 专用类型；当前用文本存储向量，保留 pgvector 导入脚本。
- 暂未接入真实 `LangGraph` 运行时；当前由后端服务函数控制选题、评分、追问、终止和报告生成。
- 当前题库仍然只有项目内置 3 道种子题，适合验证链路，不代表最终面试质量。
- 当前暂停/恢复能力通过持久化会话、轮次和 `checkpoint` 响应支持，尚未实现 LangGraph 原生 checkpoint store。

## 关键文件

- 面试模型：`backend/app/models/interview.py`
- 面试迁移：`backend/alembic/versions/20260813_0007_v01_interviews.py`
- 面试服务：`backend/app/services/interview.py`
- 面试 API：`backend/app/api/routes/interviews.py`
- API Schema：`backend/app/schemas.py`
- 后端测试：`backend/tests/test_v01_interview.py`
- 前端工作台：`frontend/src/App.tsx`
- 前端样式：`frontend/src/styles.css`

## 验证结果

后端：

```text
pytest: 36 passed
```

前端：

```text
TypeScript: passed
```

## 用户验收方式

1. 打开 `http://127.0.0.1:15173/`。
2. 确认已经上传默认简历。
3. 确认岗位池里已有岗位；如果没有，先采集岗位并点击 `确认投递`。
4. 在岗位池点击 `开始模拟面试`。
5. 在 `模拟面试` 分区回答当前问题并提交。
6. 如果回答偏弱，系统应给出追问；如果回答较完整，系统进入下一题。
7. 点击 `结束并生成报告`，或答完设定主问题数量后自动生成报告。
8. 查看报告中的总分、优势、缺口、复习建议和评分证据。

## 下一步

进入 `V0.1-6 本地联调和收尾`：

- 串联完整本地流程。
- 运行数据库迁移到最新版本。
- 补齐 README 启动和验收说明。
- 统一错误响应和状态提示。
- 评估是否在本地演示中接入真实 embedding 或继续保留规则版 fallback。
