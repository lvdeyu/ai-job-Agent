# V0.4 状态记录：模拟面试增强

更新时间：2026-08-15

## 已完成

- 扩充公共题库：
  - `knowledge/interview_question_bank/seeds/` 按方向拆分为 7 个 JSONL 种子文件（agent、agent_development_intern、langchain、llm_engineering、llm_tool_use、rag、python_backend），共 99 题。
  - 每题包含题型、技能标签、难度、参考答案、评分 Rubric、追问建议、来源和 embedding 文本。
  - `scripts/import_question_bank.py` 支持 JSONL 校验、`--write-db` 的 PostgreSQL upsert（按 `external_id` 冲突更新）和 `--with-embeddings` 的 OpenAI 兼容 embedding 生成；已用 `--write-db --with-embeddings` 写入本地 PostgreSQL（99 条全部带 1024 维 `embedding_vector`）。
- 接入真实 RAG：
  - `question_bank_items` 新增 `embedding_vector vector(1024)` 列和 HNSW 索引（迁移 `20260814_0010`）。
  - `backend/app/services/embeddings.py` 对接 OpenAI 兼容 embedding Provider（硅基流动/通用），失败抛出 `EmbeddingError` 并保留本地 fallback。
  - 检索模式三级切换：`pgvector-sql-v1`（真实 embedding 余弦距离 SQL 检索）、`pgvector-fallback-v1`（本地 32 维哈希 embedding）、`local-keyword-v1`（关键词 + 本地向量兜底）。
  - 检索结果进入 `InterviewState`，包含题库条目 ID、`retrieval_rank` 和选题原因（`decision_summary`）。
- 接入 LangGraph 原生流程：
  - `backend/app/services/interview_graph.py` 实现 `StateGraph` 节点链：load -> analyze -> retrieve -> build_plan -> select -> ask -> wait(interrupt) -> evaluate -> route -> ask_followup/select_question/generate_report -> persist_report。
  - checkpoint：PostgreSQL 用 `PostgresSaver`（`langgraph-postgres-checkpoint-v1`），SQLite/测试用 `InMemorySaver`（`langgraph-memory-checkpoint-v1`）；`thread_id` 使用面试会话 ID，支持中断恢复和主动结束。
  - 终止条件由代码控制：默认最多 8 题、单主问题最多追问 2 次、最少 5 个主问题后可提前结束、总轮次上限 `max_questions * 3`，不依赖模型决定。
- 增强报告：
  - `langgraph-report-v1`：技能维度评分（`skill_dimensions`）、事实依据（`fact_based_analysis`）与推测性评价（`inference_notes`）区分、逐题证据（题目、回答、得分、评分依据、题库 `external_id` 引用）和同岗位历史报告对比（`previous_reports`）。
  - 面试结束自动把岗位状态从 `INTERVIEWING` 流转到 `REVIEWED`。
- 补充测试：
  - `backend/tests/test_v04_pgvector_retrieval.py`：检索模式切换、embedding Provider 错误处理。
  - `backend/tests/test_v04_interview_graph.py`：路由规则全覆盖（追问/下一题/主动结束/达到上限/循环保护）、弱回答追问后结束、checkpoint 恢复 + 主动结束、同岗位两次面试历史对比、双方向岗位首题差异。
- 前端报告展示增强：技能维度、事实依据/推测性评价、题目证据（含题库引用）、同岗位历史对比，均在面试报告区展示。

## 当前实现边界

- 真实 embedding 需要 `.env` 配置 `EMBEDDING_API_KEY`/`EMBEDDING_BASE_URL`/`EMBEDDING_MODEL` 后通过 `scripts/import_question_bank.py --write-db --with-embeddings` 写入 `embedding_vector`；未配置时自动回退本地 embedding/关键词检索。
- LangGraph 节点级可观测性（节点耗时、Token 用量、检索相似度明细落库）留到 V0.5。
- 题库仍为人工维护的 JSONL 种子，管理后台留待后续版本。

## 关键文件

- 面试状态机：`backend/app/services/interview_graph.py`
- 面试服务（检索/评分/报告）：`backend/app/services/interview.py`
- Embedding Provider：`backend/app/services/embeddings.py`
- 数据库迁移：`backend/alembic/versions/20260814_0010_v04_pgvector_question_bank.py`
- 面试 API：`backend/app/api/routes/interviews.py`
- 题库导入脚本：`scripts/import_question_bank.py`
- 题库种子：`knowledge/interview_question_bank/seeds/*.jsonl`
- 后端测试：`backend/tests/test_v04_pgvector_retrieval.py`、`backend/tests/test_v04_interview_graph.py`
- 前端工作台：`frontend/src/App.tsx`

## 验证结果

后端：

```text
pytest: 54 passed
ruff: All checks passed
```

前端：

```text
TypeScript (tsc --noEmit): passed
```

## 用户验收方式

1. 启动本地依赖：`.\scripts\start_local_deps.ps1`。
2. 启动后端和前端。
3. 准备两个不同方向岗位（例如 Agent 开发 vs RAG 工程师），分别开始模拟面试，对比首题和题库引用差异。
4. 回答偏弱时确认触发合理追问；追问 2 次后不再追加。
5. 中断一次面试后通过同一会话恢复，确认从检查点继续。
6. 完成报告后查看技能维度、事实依据/推测性评价、题目证据和同岗位历史对比。
7. 同一岗位完成第二次面试后，确认报告展示 `previous_reports` 历史对比。

## 下一步

进入 `V0.5 安全、测试和可观测性`：

- Celery 异步任务链路。
- 结构化日志、限流、Prompt Injection 防护和账号注销。
- LangGraph 节点级可观测性和检索明细落库。
