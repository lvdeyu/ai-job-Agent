# ai-job-AGENT

AI 求职工作台，本地优先开发。第一版目标是跑通：

```text
注册登录 -> 上传简历 -> 配置 AI -> Boss 扩展采集 -> 岗位评测 -> 岗位池 -> 模拟面试 RAG -> 报告
```

当前阶段：`V0.4 模拟面试增强` 已完成，包含 89 题多方向题库、pgvector 语义检索、LangGraph 面试状态机和 PostgreSQL checkpoint、技能维度评分与同岗位历史报告对比。

## V0.4 模拟面试增强

- 题库：`knowledge/interview_question_bank/seeds/` 按方向拆分 7 个 JSONL 种子文件（Agent、Agent 开发实习、RAG、LangChain、LLM 工程、LLM 工具调用、Python 后端），共 99 题，每题含参考答案、评分 Rubric、追问建议和来源。
- 检索：`question_bank_items.embedding_vector vector(1024)` 存储 embedding；配置 `.env` 的 `EMBEDDING_API_KEY`/`EMBEDDING_BASE_URL`/`EMBEDDING_MODEL` 后使用 `pgvector-sql-v1` 真实语义检索，未配置时自动回退本地哈希 embedding（`pgvector-fallback-v1`）或关键词检索（`local-keyword-v1`）。
- 面试流程：LangGraph `StateGraph` 节点链（加载上下文 -> 分析目标 -> 检索题库 -> 制定计划 -> 选题 -> 提问 -> 等待回答 -> 评分 -> 路由），支持追问、下一题、主动结束和达到上限结束，终止条件全部由代码控制。
- Checkpoint：PostgreSQL 使用 `langgraph-postgres-checkpoint-v1`（`PostgresSaver`），SQLite/本地使用 `langgraph-memory-checkpoint-v1`（`InMemorySaver`）；`thread_id` 使用面试会话 ID，中断后可通过同一会话恢复。
- 报告：`langgraph-report-v1`，包含技能维度评分、事实依据与推测性评价区分、逐题证据（题库引用 + 回答引用 + 评分依据）和同岗位历史报告对比。
- 导入题库（可选生成真实 embedding）：

```powershell
D:\python3.12\python.exe scripts\import_question_bank.py --write-db --with-embeddings
```

## 本地依赖

- Python `>=3.12,<3.13`
- Node.js `>=18`
- Docker Desktop

## M0 启动方式

启动本地依赖服务：

```powershell
.\scripts\start_local_deps.ps1
```

启动后端：

```powershell
cd backend
D:\python3.12\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 18000
```

如果当前环境无法创建 `.venv`，可以临时使用项目内依赖目录：

```powershell
cd backend
D:\python3.12\python.exe -m pip install --target .deps -e ".[dev]"
$env:PYTHONPATH="$PWD\.deps;$PWD"
D:\python3.12\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18000
```

启动前端：

```powershell
cd frontend
npm install
npm run dev
```

本地开发时，前端默认访问 `http://127.0.0.1:15173`，API 请求默认访问 `http://127.0.0.1:18000`。

浏览器扩展开发构建：

```powershell
cd browser-extension
npm install
npm run build
```

扩展构建后，在 Chrome/Edge 的扩展管理页开启开发者模式，并加载：

```text
D:\Users\codex\workspace\ai-job-AGENT\browser-extension\dist
```

## Boss 岗位采集前准备

1. 启动后端 `http://127.0.0.1:18000` 和前端 `http://127.0.0.1:15173`。
2. 在 Chrome/Edge 中加载 `browser-extension/dist` 扩展。
3. 在同一个浏览器里打开 Boss 直聘并手动登录。
4. 如果 Boss 出现验证码或安全验证，先手动完成。
5. 回到 ai-job-AGENT 工作台，点击“重新检测扩展”，显示扩展已连接后再开始采集。

说明：扩展只读取 Boss 搜索页面当前可见的岗位卡片，不读取或上传 Boss 密码、Cookie、聊天记录，也不会自动投递简历。

## 验证命令

```powershell
cd backend
$env:PYTHONPATH="$PWD\.deps;$PWD"
D:\python3.12\python.exe -m pytest -q
.\.tools\Scripts\ruff.exe check app tests alembic\env.py --no-cache
D:\python3.12\python.exe -m alembic upgrade head
```

```powershell
cd frontend
npm exec tsc -- --noEmit
npm exec vite -- build --outDir ../tmp/frontend-build-v01 --emptyOutDir false
```

```powershell
python scripts/import_question_bank.py
python scripts/import_question_bank.py --write-db --with-embeddings
```

也可以一次执行 M0 可用检查：

```powershell
.\scripts\check_m0.ps1
```
