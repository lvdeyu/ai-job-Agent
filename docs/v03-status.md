# V0.3 状态记录：岗位池和 Boss 采集稳定性

更新时间：2026-08-14

## 已完成

- 完善岗位池状态流转：
  - 支持 `NEW`、`SCORED`、`REVIEWED`、`CONFIRMED`、`APPLIED`、`INTERVIEWING`、`OFFER`、`REJECTED`、`ARCHIVED`。
  - 岗位加入岗位池时自动设为 `CONFIRMED`，AI 测评后自动流转为 `SCORED`。
  - 开始模拟面试自动流转为 `INTERVIEWING`，结束模拟面试自动回到 `REVIEWED`。
  - 用户手动标记的 `REJECTED`、`ARCHIVED`、`OFFER` 不会被自动流转覆盖。
  - 每次状态变化记录 `status_changed_at`，后续可扩展审计。
- 支持投递跟进信息：
  - 岗位池内可保存投递时间、本次使用的简历版本、联系人和备注。
  - 前端岗位卡片新增“投递跟进”编辑区，状态、投递日期、简历版本、联系人、备注均可直接保存。
  - 简历版本选择复用现有默认简历和岗位级简历版本列表，不会覆盖原简历。
- 强化岗位池筛选：
  - 后端 `GET /api/v1/jobs/pool` 支持 `status`、`keyword`、`company`、`city`。
  - 前端岗位池提供状态、公司、城市、岗位名/标签/JD 关键词筛选。
- 强化岗位去重：
  - 有 `source_job_id` 时优先使用 `user_id + source_job_id` 去重。
  - 没有来源 ID 时使用公司、标题、城市和 JD 摘要生成指纹去重。
  - 搜索结果和岗位池引用同一岗位记录，重复采集只标记重复，不新增记录。
- 完善 Boss 扩展采集稳定性：
  - 采集会话支持幂等键：重复创建会话复用已有会话，重复提交批次直接返回已有统计。
  - 采集会话记录扩展版本、适配器名称、适配器启用快照和分页上限。
  - 后端拒绝旧版扩展（HTTP 426），限制单用户采集会话频率（HTTP 429），适配器停用时拒绝创建任务（HTTP 503）。
  - `AUTH_REQUIRED`、`CAPTCHA_REQUIRED`、`RATE_LIMITED`、`SOURCE_CHANGED`、`NO_RESULT` 等异常状态只记录失败，不写入岗位数据。
  - 浏览器扩展提交结果时带上 `idempotency_key` 和 `extension_version`。
- 前端采集体验：
  - 开始采集前先检查后端适配器状态，停用时直接给出明确提示。
  - 扩展心跳返回扩展版本，创建采集会话时上传扩展版本。
  - 采集结果和历史记录对失败类状态显示明确文案和颜色。
- 补充 V0.3 后端测试：
  - 岗位池元信息保存和用户隔离。
  - 岗位池服务端筛选。
  - 模拟面试自动推动岗位状态。
  - 会话幂等、提交幂等。
  - 来源 ID 和指纹双重去重。
  - 异常采集状态不写入岗位。
  - 适配器停用、版本过低和单用户限速。

## 当前实现边界

- 采集适配器开关仍为配置文件/环境变量驱动（`boss_adapter_enabled`），没有独立管理后台页面。
- 采集会话超时沿用现有 15 分钟 Token 有效期；扩展侧仍由工作台手动触发，无后台轮询心跳任务。
- 岗位池状态变化只记录时间，未落审计明细表。
- 真实 Celery Worker、真实 embedding、`pgvector` 专用列和 LangGraph 原生 checkpoint 仍留到后续版本。

## 关键文件

- 岗位模型和采集会话模型：`backend/app/models/job_collection.py`
- 数据库迁移：`backend/alembic/versions/20260814_0009_v03_job_pool_collection_stability.py`
- 岗位池 API：`backend/app/api/routes/jobs.py`
- 采集 API：`backend/app/api/routes/job_collections.py`
- 模拟面试服务：`backend/app/services/interview.py`
- API Schema：`backend/app/schemas.py`
- 后端测试：`backend/tests/test_v03_job_pool_collection_stability.py`
- 前端工作台：`frontend/src/App.tsx`
- 前端样式：`frontend/src/styles.css`
- 浏览器扩展：`browser-extension/src/background.ts`

## 验证结果

后端：

```text
pytest: 44 passed
ruff: All checks passed
```

前端：

```text
TypeScript + Vite build: passed
```

浏览器扩展：

```text
TypeScript: passed
```

仓库：

```text
git diff --check: passed
```

运行态（2026-08-14，本地 PostgreSQL 已升级到 `20260814_0009`）：

- 使用新代码在 `127.0.0.1:18001` 临时启动后端，完成 29 项接口验收，全部通过。
- 覆盖：未登录适配器状态返回 401、注册登录、采集会话幂等、提交幂等、来源 ID 去重、指纹去重、岗位池状态/公司/城市/关键词筛选、岗位池元信息保存、模拟面试状态流转、异常采集不写入、旧扩展版本 426、用户数据隔离。
- `127.0.0.1:18000` 常驻后端已重启并加载新代码，`/health` 正常，`adapter-status` 未登录返回 401、登录后返回 `enabled=true`。
- V0.3 代码已提交并推送到 `github.com:lvdeyu/ai-job-Agent.git` 的 `master`。

## 用户验收方式

1. 启动本地依赖：`.\scripts\start_local_deps.ps1`。
2. 启动后端、前端，并在 Chrome/Edge 加载 `browser-extension/dist`。
3. 注册或登录，上传默认简历。
4. 采集同一个关键词两次，确认第二次只标记重复、不新增岗位和岗位池记录。
5. 在岗位池修改状态、投递时间、联系人、备注和使用简历，刷新后确认保存。
6. 开始并结束一次模拟面试，确认岗位状态自动从 `INTERVIEWING` 回到 `REVIEWED`。
7. 模拟未登录、验证码、限速或页面结构变化，确认采集结果给出明确状态且不写入脏数据。
8. 修改 `.env` 中 `BOSS_ADAPTER_ENABLED=false` 后重启后端，确认前端提示采集服务不可用。

## 下一步

进入 `V0.4 模拟面试增强`：

- 使用 LangGraph 管理提问、追问、跳题和结束状态。
- 完善面试状态快照、PostgreSQL 检查点和中断恢复。
- 引入更真实的 RAG 检索和题目生成。
