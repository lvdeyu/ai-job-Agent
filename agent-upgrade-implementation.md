# ai-job-AGENT Agent 化落地实施方案

更新时间：2026-08-18

## 1. 方案定位

上一份 `docs/agent-portfolio-architecture.md` 讲了"理想面试 Agent 应该长什么样"，
这份文档把理想设计**映射到本项目的实际文件和现有函数**，给出可执行的分阶段改造
方案。原则是：复用不重写、决策权迁移、确定性能力工具化、旧接口兼容。

一句话目标：

> 把 `interview_graph.py` 里"规则决策"的节点，改造成"LLM 生成 + 规则审批 + 工具执行"
> 的真实 Agent 循环，并把前端从"题目表单"升级为"对话式面试页"。

## 2. 理想设计与现状映射

| 理想模块 | 本项目现有落点 | 现状 | 改造动作 |
| --- | --- | --- | --- |
| 大脑 LLM | `model_connection.py` / `embeddings.py` | 只有连接测试和向量化 | 新增 `app/services/llm/` 网关，接 chat/stream/tool call，复用 `ModelProviderConfig` |
| 岗位说明书 | `SKILL_VOCABULARY`、评分 rubric、路由阈值 | 散落在代码里 | 新增 `app/prompts/` 版本化模板 + `context_assembler.py` |
| 记忆 | `InterviewState` + LangGraph checkpoint | 只有会话内状态 | 新增 `interview_messages`、`user_interview_memory` 两层记忆 |
| 知识库 | 题库 JSONL + pgvector | 只有题库 | 新增简历项目提取 `resume_project_items`；JD 事实复用现有字段 |
| 手脚 Tools | 无工具调用 | 检索/评分/路由硬编码 | 新增 `app/services/tools/` 注册表 + 6 个白名单工具 |
| 对话体验 | `App.tsx` 题目 + TextArea 表单 | 非对话 | 新增 `InterviewChat` 组件 + SSE chat 端点 |
| 评估 | `tests/test_v04_interview_graph.py` 等 | 无 Agent 行为测试 | 新增 `tests/agent_evals/`（fake LLM + golden + guardrail + judge） |
| 可观测 | `observability.py` 请求日志 | 无 Agent trace | 新增 `agent_event_log` 表 + 前端过程还原视图 |
| 依赖 | `pyproject.toml` | langgraph 未声明 | 补齐 langgraph / checkpoint 依赖 |

## 3. 分模块改造方案（文件级）

### 3.1 大脑：LLM 服务层

新增目录 `backend/app/services/llm/`：

```text
llm_client.py       # 统一接口：chat / structured / stream / with_tools
providers/
  openai_compatible.py   # openai / deepseek / tongyi
  anthropic.py           # claude
response_schema.py       # 结构化输出校验 + 自动重试一次
fallback.py              # 无配置/失败 -> 规则流
```

接线点：

- `model_connection.py` 只保留连接测试，不再承担业务调用。
- `app/api/routes/jobs.py` 的 `_get_model_provider` 提取为公共依赖
  `app/api/deps.py` 的 `get_active_model_provider`，面试创建和 chat 共用。
- `create_interview_session`（`services/interview.py`）读取模型配置，写入
  `InterviewSession` 新增字段 `llm_provider_id`。

### 3.2 岗位说明书：Prompt 资产

新增 `backend/app/prompts/`：

```text
hr_system_v1.md          # HR 角色、语气、边界
interview_plan_v1.md     # 输出面试计划
ask_question_v1.md       # 输出开场白/题目/追问/结束语
judge_answer_v1.md       # 输出评分解释与证据命中
closing_v1.md            # 反问环节与收尾
context_assembler.py     # 组装 JD/简历/评测/历史/记忆，控制 token
```

改造点：

- `interview_graph.py` 中 `analyze_interview_targets`、`select_question`、
  `ask_followup` 节点保留"规则兜底"，但优先调用 LLM 生成计划/发言。
- 现有 `SKILL_VOCABULARY`、`route_next_step` 阈值降级为 guardrails 输入，
  不再作为唯一决策来源。

### 3.3 记忆：三层记忆

短期（会话内）：

- `InterviewState` 增加 `chat_messages`、`current_phase`、`pending_tool_calls`。
- 沿用现有 `PostgresSaver / InMemorySaver` checkpoint。

中期（对话流水）：

- 新表 `interview_messages`：role、content、turn_id、phase、token_count。
- `submit_interview_answer` 与新的 chat 端点每次写入，刷新页面从该表重建上下文。

长期（跨场记忆）：

- 新表 `user_interview_memory`：user_id、job_id、skill、strength_score、
  weak_points、last_session_id。
- `generate_interview_report` 节点结束时写入；下一场 `context_assembler`
  携带"上次 X 技能偏弱，重点考察"。

### 3.4 知识库：三类知识

- 题库：现有 `question_bank_items` 保留，`import_question_bank.py` 增加
  `question_category`（knowledge/project）字段。
- 简历项目：新增 `backend/app/services/knowledge/resume_projects.py`：
  1. 规则切分 `ResumeVersion.extracted_text` 的项目段落；
  2. LLM 抽取项目名、职责、技术栈、成果、风险点；
  3. 写入 `resume_project_items` 表并向量化。
- JD 事实：复用 `job.description/tags/salary` 与 `job_evaluation.raw_report_json`
  摘要，在 `context_assembler` 中注入，不进向量库。
- 检索：`retrieve_interview_questions`（`services/interview.py`）保持，新增
  `resume_project_items` 检索，供项目拷打工具使用。

### 3.5 手脚：工具注册表

新增 `backend/app/services/tools/`：

```text
registry.py           # 工具 JSON schema 注册
interview_tools.py    # 6 个工具实现
```

工具清单：

| 工具 | 封装现有代码 | 权限 |
| --- | --- | --- |
| `search_interview_questions` | `retrieve_interview_questions` | 只读题库 |
| `get_resume_projects` | 新 `resume_project_items` 查询 | 只读当前用户简历 |
| `get_job_context` | `Job` + `JobEvaluation` 查询 | 只读当前会话岗位 |
| `score_answer` | `evaluate_interview_answer` | LLM 只能请求，不能改分 |
| `save_memory_note` | 新长期记忆写入 | 仅结构化字段 |
| `finish_interview` | 现有 finish 流程 | 受阶段/题数约束 |

接线点：

- `interview_graph.py` 新增 `llm_decide` 节点：绑定工具，输出
  `tool_call` 或 `message`；
- 新增 `tool_executor` 节点：执行工具并把结果回填状态；
- 新增 `guardrail` 节点：校验 LLM 提议的动作（题数、追问深度、阶段、权限）。

### 3.6 前端：对话式面试页

改造 `frontend/src/App.tsx` 的"模拟面试"区（当前是题目 + TextArea + 历史表格）：

- 新增 `frontend/src/components/InterviewChat.tsx`：
  - 消息气泡流（HR 开场白、题目、追问、用户回答、思考中指示器）；
  - 阶段胶囊（开场白 / 提问 / 项目拷打 / 反问 / 结束）；
  - SSE 客户端（fetch + ReadableStream），刷新后从 messages 恢复；
  - 快捷操作：发送、结束面试、查看报告。
- 保留现有报告展示，报告阶段再显示题目引用和评分证据。

### 3.7 API：chat 端点

`backend/app/api/routes/interviews.py` 新增：

```text
POST /api/v1/interviews/{session_id}/chat
  request: { "content": "...", "action": "answer" | "finish" | "skip" }
  response: SSE events
    phase | thinking_start | assistant_delta | tool_used
    | assistant_end | session_state | error | done

GET  /api/v1/interviews/{session_id}/messages   # 重连恢复
```

`schemas.py` 增加 `ChatMessageRequest`、`ChatEventResponse` 等类型。
旧 `POST /answers`、`POST /finish` 保留，作为兼容路径和规则降级路径。

### 3.8 测试与评估

新增 `backend/tests/agent_evals/`：

```text
fake_llm.py           # 注入预定义 LLM 响应
test_golden_flows.py  # 开场 -> 知识题 -> 项目题 -> 反问 -> 报告
test_guardrails.py    # 超上限追问、访问他人数据、过早结束被拒绝
test_fallback.py      # 无模型配置时降级规则流
test_judge_evals.py   # LLM-as-judge 质量基线
```

现有 54 个测试保持全绿；新增测试重点验证"工具调用顺序 + 状态流转 + 护栏生效"。

### 3.9 可观测性

- 新表 `agent_event_log`：节点名、LLM 调用、工具调用、入参/出参摘要、耗时、
  token、成本、错误。
- `app/core/observability.py` 增加 Agent 事件写入器。
- 前端"过程还原"面板按时间轴展示，Phase 4 完成。

### 3.10 依赖与复现

`backend/pyproject.toml` 增加：

```text
langgraph
langgraph-checkpoint-postgres
langchain-core
```

保证新环境 `pip install -e ".[dev]"` 后 `interview_graph.py` 可导入。

## 4. 数据库迁移

新增 `backend/alembic/versions/20260818_0011_agent_upgrade.py`：

- `interview_sessions`：`phase`、`current_question_type`、`llm_provider_id`；
- `interview_turns`：`turn_category`（intro/knowledge/project/followup/closing）；
- 新表：`interview_messages`、`resume_project_items`、`user_interview_memory`、
  `agent_event_log`；
- `question_bank_items`：`question_category`。

## 5. 分阶段实施计划

### Phase 0：LLM 网关 + 对话页（1-2 天，先可演示）

- `services/llm/` 网关 + 降级；
- `prompts/hr_system_v1`、`ask_question_v1`、`closing_v1`；
- `POST /interviews/{id}/chat`（SSE）+ `InterviewChat` 组件；
- 知识题沿用 `retrieve_interview_questions`，评分沿用规则。

验收：

```text
用户从岗位池开始面试
-> 看到 HR 开场白和自我介绍引导
-> 对话完成知识题、追问、反问
-> 结束生成报告
```

### Phase 1：简历项目拷打（2-3 天）

- `resume_projects.py` 提取 + 新表 + 向量化；
- `get_resume_projects` 工具；
- 四阶段状态机完整化：opening -> probing -> wrap_up -> report；
- `prompts/interview_plan_v1`、`ask_question_v1` 支持项目题。

验收：

```text
HR 能基于简历项目连续追问
（负责模块、技术难点、怎么解决）
项目题不引用简历外事实
```

### Phase 2：长期记忆（2-3 天）

- `user_interview_memory` 读写；
- `generate_interview_report` 结束写入；
- `context_assembler` 注入历史弱项。

验收：

```text
同一岗位第二次面试，HR 主动提到上次弱项并针对性出题
```

### Phase 3：工具循环 + LLM-as-judge + 护栏（2-3 天）

- `llm_decide` / `tool_executor` / `guardrail` 节点；
- `score_answer` 工具 + `judge_answer_v1`；
- `tests/agent_evals/` 全绿。

验收：

```text
工具调用顺序和状态流转测试通过
连续让模型超上限，guardrail 测试证明被拒绝
无模型配置时降级规则流完成面试
```

### Phase 4：可观测 + 演示 + 文档（1-2 天）

- `agent_event_log` + 前端过程还原；
- demo seed（示例岗位 + 带项目的简历 + 题库）+ `start_demo.ps1`；
- README 更新 + 架构文档 + "Agent vs Workflow" 章节。

验收：

```text
一键启动后可完整演示：
对话面试 -> 项目拷打 -> 追问 -> 反问 -> 带证据报告 -> 过程回放
```

## 6. 关键风险与对策

| 风险 | 对策 |
| --- | --- |
| 模型不可用 / 接口失败 | 规则流降级，旧接口保持可用 |
| 模型成本与延迟 | SSE 流式 + 上下文裁剪 + 每轮 token 预算 |
| 项目题编造简历事实 | 只允许引用 `resume_project_items`，工具返回原文字段 |
| 评分不可复现 | `score_answer` 确定性工具 + LLM-as-judge 只做解释 |
| 模型重复追问导致死循环 | guardrail 上限 + 总轮次保护（沿用现有 `max_questions * 3`） |
| 简历/JD 内容注入 prompt | system prompt 明确"内容只是数据"，增加注入测试用例 |
| 前端大改影响现有功能 | 先新增 `InterviewChat`，旧表单保留到验收通过 |

## 7. 最终验收清单

对照 8 条 Agent 硬指标：

1. LLM 决策：开场/选题/追问/收尾文案由 LLM 生成，报告中可查到对应 `prompt_version`。
2. 工具行动：`agent_event_log` 能回放出 `search_*` / `score_answer` 等工具调用。
3. 记忆：刷新页面可恢复会话；第二场面试引用上次弱项。
4. 知识：报告包含题库引用与简历项目引用，均可溯源。
5. 控制护栏：guardrail 测试证明超上限动作被拒绝。
6. 可评估：`tests/agent_evals/` 全绿，现有 54 个测试保持全绿。
7. 可观测：前端可回放一次完整面试过程。
8. 可演示：`start_demo.ps1` 一键启动，完整走通对话面试到报告。

完成以上 8 条，这个项目就从"带 LangGraph 外形的确定性工作流"变成
**LLM 决策、工具行动、有记忆、有知识、可评估、可观测、可演示的 Agent 作品**。
