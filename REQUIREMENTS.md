# ai-job-AGENT 需求文档

## 1. 文档信息

- 项目名称：`ai-job-AGENT`
- 文档版本：`v0.8`
- 文档状态：开发基线
- 目标用户：需要寻找实习或全职工作的个人用户
- 首要目标：帮助用户针对具体岗位完成岗位分析、简历评测和模拟面试

## 2. 产品定位

`ai-job-AGENT` 是一个面向求职者的 AI 求职工作台。用户维护自己的求职偏好和简历，在系统内搜索 Boss 直聘岗位；每个搜索结果都可以直接进行 AI 简历匹配评测，或确认投递并进入个人岗位池。岗位池集中展示岗位、评测和简历优化建议，并提供针对该岗位的专属模拟面试。

项目的核心不是“调用一次大模型”，而是形成可追踪的工作流：

```text
个人资料/简历 -> Boss 岗位搜索 -> AI 匹配评测/确认投递 -> 个人岗位池
                                     |                    |
                                     v                    v
                              简历优化建议          岗位专属模拟面试
                                     |                    |
                                     v                    v
                              用户手动修改          面试评分报告
```

## 3. 目标与非目标

### 3.1 目标

1. 支持多个用户注册和数据隔离。
2. 支持 OpenAI、通义、DeepSeek、Claude 等模型供应商。
3. 支持 `.docx`、`.md`、`.pdf` 简历上传和内容抽取。
4. 支持在系统内搜索 Boss 直聘岗位，并对搜索结果进行岗位级简历评测。
5. 支持岗位确认投递、岗位池管理和已投递岗位过滤。
6. 支持基于 JD、简历和通用题库的专属模拟面试。
7. 第一版支持本地运行完整闭环；后续版本再支持部署到云服务器，并具备基本的安全、日志、备份和监控能力。

### 3.2 非目标

1. 第一版不自动替用户提交真实简历或自动发送消息。
2. 第一版不承诺高频、无限量抓取招聘网站。
3. 第一版不让 AI 自动覆盖用户简历，AI 只提供评测和建议。
4. 第一版不追求训练自有大模型，使用外部模型供应商。
5. 第一版不拆分成复杂微服务，优先使用模块化单体完成闭环。
6. 第一版不做公开网页搜索、搜索引擎抓取或手动导入作为 Boss 搜索降级方案。

## 4. 已确定的产品假设

以下假设用于启动开发，后续可以在迭代中调整：

- 第一版使用邮箱和密码注册登录。
- 第一版岗位来源只支持 Boss 直聘浏览器扩展增强采集，不开发公开搜索降级、手动录入和 CSV 导入功能。
- Boss 直聘采集采用独立适配器、用户主动触发、低频、可配置的方式开发。
- 第一版只要求本地运行，不部署到服务器。
- 本地环境使用 Docker Compose 启动 PostgreSQL、Redis、MinIO 等依赖服务。
- 云服务器、生产域名、HTTPS、备份和回滚方案放到 V1.0 正式上线版本处理。
- 默认后端采用 `FastAPI`，前端采用 `React + TypeScript`。
- 默认数据库为 `PostgreSQL`，向量检索使用 `pgvector`。

## 5. 用户角色

### 5.1 普通用户

- 注册、登录、退出登录
- 管理个人求职配置和简历
- 配置 AI 供应商
- 搜索 Boss 直聘岗位并进行评测
- 管理岗位投递池
- 进行模拟面试并查看报告

### 5.2 管理员（后续版本）

- 查看系统任务和错误日志
- 管理模型供应商白名单
- 管理公共面试题库
- 查看基础使用统计

## 6. 功能需求

### 6.1 账户与多租户

需求编号：`AUTH`

- 用户可以使用邮箱和密码注册、登录、退出。
- 密码必须使用安全哈希存储，不能保存明文密码。
- 登录后所有业务数据必须按 `user_id` 隔离。
- Token 过期后需要返回明确错误，不能静默使用其他用户数据。
- 后续可以扩展邮箱验证、找回密码和第三方登录。

验收标准：用户 A 无法通过修改请求参数读取或修改用户 B 的简历、岗位、评测和面试记录。

### 6.2 个人配置

需求编号：`PROFILE`

用户可以维护：

- 目标岗位，例如 Agent 开发、AI 应用开发、Java 后端
- 期望薪资范围
- 工作城市，可多选
- 工作形式：实习、全职、均可
- 技能标签
- 掌握的自然语言及熟练程度
- 行为和文化偏好，例如自主性、质量导向、协作方式
- 不可接受条件（Deal-breakers），例如 996、纯 On-call、外包
- 通勤距离、远程办公和时差偏好
- 教育经历和可选的个人介绍

配置需要支持保存、修改和查询，并作为岗位匹配时的辅助条件。

### 6.3 简历管理

需求编号：`RESUME`

- 支持上传 `.docx`、`.md`、`.pdf`。
- 校验文件类型、大小和文件名，拒绝未知格式。
- 抽取文本并保存原始文件和结构化内容。
- 结构化内容至少包含：基本信息、教育经历、技能、工作经历、项目经历。
- 用户可以设置默认简历。
- 用户可以查看、删除和创建简历版本。
- 删除简历时必须同步处理文件和关联任务，避免产生孤立数据。

说明：PDF 解析需要兼容文本型 PDF；扫描件 OCR 作为后续能力，不作为首版硬性要求。

### 6.4 AI 供应商配置

需求编号：`MODEL`

供应商配置字段：

- 供应商类型：OpenAI、通义、DeepSeek、Claude、自定义
- API Key
- 模型名称
- Base URL
- 请求超时时间
- 是否启用

功能要求：

- 用户可以新增、修改、启用和停用配置。
- API Key 在数据库中加密保存，页面只显示脱敏结果。
- 提供“连接测试”按钮。
- 连接测试返回成功、超时、认证失败、模型不存在等可理解的错误类型。
- 业务请求必须通过统一的供应商适配接口调用。
- 日志中不得打印完整 API Key 和完整用户简历。

### 6.5 Boss 岗位搜索与采集

需求编号：`JOB`

浏览器扩展、采集会话、状态恢复和交互文案的详细设计见 [`docs/boss-browser-collector.md`](docs/boss-browser-collector.md)。

第一版仅支持在系统内搜索 Boss 直聘岗位，不提供手动录入、粘贴 JD 或 CSV 导入入口。

用户可以输入：

- 搜索关键词，例如 Agent 开发、AI 应用开发、Java 后端
- 工作城市
- 薪资范围
- 工作形式：实习、全职
- 经验和学历条件（在来源支持时使用）

搜索结果列表中的每个岗位必须提供两个主操作：

1. `AI 测评`：使用用户选择的简历评测岗位匹配度，并展示简历优化建议。
2. `确认投递`：把岗位加入当前用户的岗位池；系统本身不向 Boss 自动提交简历。

搜索结果还需要展示该岗位是否已评测、是否已进入岗位池，避免用户重复处理。

岗位标准字段：

- 标题
- 公司名称
- 原始 JD
- 清洗后的 JD
- 城市
- 薪资范围
- 工作形式
- 来源
- 来源链接
- 发布时间（如果来源提供）
- 来源岗位唯一标识（如果来源提供）
- 唯一指纹，用于去重
- 岗位状态
- 首次采集时间和最后采集时间

Boss 适配器要求：

- 使用独立的 `JobSourceAdapter` 接口，不把 Boss 逻辑写进核心业务。
- 当前不把任何未经 Boss 官方确认的第三方接口作为正式依赖；如果未来取得官方授权 API，优先新增 API Adapter。
- 第一版采用浏览器侧采集：用户安装浏览器扩展，系统把搜索条件发送给扩展，扩展在用户自己的 Boss 页面中读取当前可见岗位。
- 扩展可以打开或复用 Boss 搜索页面，但不自动填写账号密码，不上传 Cookie，不绕过登录、验证码或安全验证。
- 扩展采集到的岗位先发送到后端临时采集会话，再由后端标准化、校验、去重后返回工作台。
- 默认每次采集 `20` 个岗位，用户可选 `10/20/50`，单次硬上限 `50`，默认最多处理 `3` 页。
- 采集必须支持单用户限速、扩展心跳、分页上限、缓存、有限重试和失败记录。
- 页面结构或来源字段变化时，扩展和适配器必须停止写入不完整岗位，并返回 `SOURCE_CHANGED`。
- 不绕过验证码、登录保护或其他安全机制。
- 来源要求验证或出现验证码时，任务立即停止并向用户展示 `AUTH_REQUIRED` 或 `CAPTCHA_REQUIRED`。
- 第一版不提供手动导入降级功能，因此 Boss 搜索不可用时需要显示服务不可用提示。
- 搜索前必须执行预检：扩展安装状态、扩展权限、Boss 登录状态、当前页面域名、采集数量和本次限流状态。
- 预检未通过时不能直接开始采集，必须显示下一步操作提示。
- 具体上线策略必须遵守目标网站服务条款和适用法律。

采集结果状态：`QUEUED`、`RUNNING`、`AUTH_REQUIRED`、`CAPTCHA_REQUIRED`、`RATE_LIMITED`、`PARTIAL_SUCCESS`、`SUCCESS`、`NO_RESULT`、`SOURCE_CHANGED`、`FAILED`。

采集前引导弹窗：

```text
标题：采集 Boss 岗位前，请完成以下准备

1. 安装并启用 ai-job-AGENT 浏览器扩展。
2. 在当前浏览器中登录 Boss 直聘。
3. 如 Boss 显示验证码或安全验证，请先手动完成。
4. 采集过程中请不要关闭 Boss 搜索页面。
5. 本次默认采集 20 个岗位，你可以调整为 10、20 或 50。

隐私说明：扩展只读取本次搜索页面中可见的岗位信息，
不会读取或上传你的 Boss 密码、Cookie、聊天记录。
```

状态对应的用户提示：

| 状态 | 用户提示 | 可执行操作 |
|---|---|---|
| 扩展未安装 | 未检测到采集扩展，请先安装并刷新页面。 | 查看安装指引、重新检测 |
| 扩展未授权 | 扩展尚未获得 Boss 页面访问权限。 | 打开扩展授权页 |
| `AUTH_REQUIRED` | Boss 需要登录，请在新打开的 Boss 页面完成登录。我们不会读取或保存你的密码。 | 打开 Boss、重新检测 |
| `CAPTCHA_REQUIRED` | Boss 要求安全验证，请手动完成后返回继续。系统不会尝试绕过验证。 | 打开验证页面、重新检测 |
| `RUNNING` | 正在采集岗位，请保持 Boss 页面开启。 | 取消采集 |
| `PARTIAL_SUCCESS` | 已采集部分岗位，剩余岗位因页面限制未能获取。 | 查看结果、稍后重试 |
| `NO_RESULT` | 搜索已成功，但没有找到符合当前条件的岗位。 | 修改搜索条件 |
| `RATE_LIMITED` | 访问过于频繁，请稍后再试。 | 查看等待时间 |
| `SOURCE_CHANGED` | Boss 页面结构可能已变化，采集功能暂时不可用。 | 反馈问题、稍后重试 |
| `SUCCESS` | 岗位采集完成，已自动过滤重复岗位。 | 查看岗位 |
| `FAILED` | 本次采集失败，已有岗位和评测数据不会受到影响。 | 查看原因、重新尝试 |

### 6.6 岗位分析和简历评测

需求编号：`EVALUATION`

评测必须以 [`knowledge/evaluation_framework_cn.md`](knowledge/evaluation_framework_cn.md) 作为唯一业务判定标准。Prompt 可以迭代，但不能在未修改并评审该标准的情况下改变维度、权重、Deal-breaker 或诚实原则。

具体的 Agent 编排、节点和失败路径见 `7.7.2 JobEvaluationGraph`。

用户在搜索结果或岗位池点击 `AI 测评`，选择一份简历（默认选中默认简历）后，系统需要：

1. 从 JD 中提取岗位职责、硬技能、软技能、经验要求、学历要求、薪资、地点、工作强度信号和加分项。
2. 将 JD 与简历、个人画像、求职偏好和 Deal-breakers 进行比较。
3. 按固定七维权重计算原始加权分。
4. 检查语言闸门和 Deal-breakers，命中时将最终总分强制限制为不高于 30。
5. 输出匹配项、缺失项、事实证据、风险和简历优化建议。
6. 记录评估框架版本、模型、Prompt 版本、时间和原始输入摘要，支持结果追踪。

固定评分维度和权重：

| 维度 | 权重 |
|---|---:|
| 技能匹配 | 30% |
| 经验匹配 | 25% |
| 行为文化 | 15% |
| 薪资结构 | 10% |
| 工作强度 | 10% |
| 稳定性与合规 | 5% |
| 通勤与城市 | 5% |

计算规则：

```text
原始加权分 = Σ(维度得分 × 维度权重)
最终总分 = 命中任一 Deal-breaker 或语言闸门 ? min(原始加权分, 30) : 原始加权分
```

建议等级默认映射：

- `85-100`：强烈投递
- `70-84`：可投递
- `50-69`：观望
- `0-49`：不建议

当某个维度缺少可靠事实时，必须标记 `insufficient_data`，使用中性分 `50` 参与加权，并在风险中说明信息不足。不得把未知信息描述成已确认的优点或缺点。

建议输出字段：

```json
{
  "framework_version": "v1",
  "raw_weighted_score": 0,
  "final_score": 0,
  "recommendation": "强烈投递 | 可投递 | 观望 | 不建议",
  "one_sentence_reason": "",
  "language_gate_triggered": false,
  "dealbreakers_hit": [],
  "dimensions": {
    "skill_match": {"score": 0, "weight": 0.30, "data_status": "sufficient", "explanation": ""},
    "experience_match": {"score": 0, "weight": 0.25, "data_status": "sufficient", "explanation": ""},
    "behavioral_culture": {"score": 0, "weight": 0.15, "data_status": "sufficient", "explanation": ""},
    "compensation": {"score": 0, "weight": 0.10, "data_status": "sufficient", "explanation": ""},
    "work_intensity": {"score": 0, "weight": 0.10, "data_status": "sufficient", "explanation": ""},
    "stability_compliance": {"score": 0, "weight": 0.05, "data_status": "insufficient_data", "explanation": ""},
    "commute_city": {"score": 0, "weight": 0.05, "data_status": "sufficient", "explanation": ""}
  },
  "highlights": [],
  "risks_and_gaps": [],
  "salary_benchmark": {"value": "", "is_estimate": false, "evidence": ""},
  "evidence": [],
  "resume_focus_suggestions": [],
  "honest_gap_statements": []
}
```

要求：

- 模型输出必须经过 JSON Schema 校验。
- JSON 解析失败需要重试或返回可理解的失败状态。
- 评分结果必须展示理由，不允许只展示一个分数。
- 后端必须重新计算加权分和封顶规则，不能直接信任模型给出的总分。
- Deal-breaker 和语言闸门命中结果必须在页面显著展示。
- 薪资没有可靠数据时必须标记为估算；不能生成看似精确但无依据的数字。
- 缺口必须如实展示，不能为了提高投递建议而弱化缺口。
- 评测结果需要支持历史查看。
- 同一个岗位在搜索结果和岗位池中必须引用同一份评测记录，不能产生互不关联的数据副本。
- 用户更换简历版本后可以重新评测，并明确显示本次评测使用的简历版本。

### 6.7 简历版本和用户手动修改

需求编号：`RESUME_VERSION`

- AI 只能生成修改建议，不直接覆盖用户内容。
- 用户可以复制一份岗位专属简历版本。
- 用户可以手动编辑版本内容。
- 每次保存生成版本号和修改时间。
- 用户可以对修改后的版本再次评测。
- 评测页面需要对比原版本和当前版本的分数变化。

### 6.8 岗位投递池

需求编号：`APPLICATION`

岗位状态建议：

```text
NEW -> SCORED -> REVIEWED -> CONFIRMED -> APPLIED
                         \-> REJECTED
```

- 用户可以确认“准备投递”或“已投递”。
- 确认后的岗位进入个人岗位池。
- 后续搜索到相同岗位时必须标记为已进入岗位池，不能重复添加。
- 用户可以记录投递时间、使用的简历版本、联系人和备注。
- 支持按状态、公司、城市和岗位名称筛选。
- 岗位池详情必须展示已有 AI 匹配评测和简历优化建议。
- 岗位池详情支持重新评测，并保留历史评测记录。
- 岗位池中的每个岗位必须提供 `模拟面试` 入口。
- 第一版不自动替用户向招聘网站提交简历。

### 6.9 专属模拟面试

需求编号：`INTERVIEW`

具体的状态、节点、路由、终止条件和检查点要求见 `7.7.3 InterviewAgentGraph`。

题目生成输入：

- 岗位 JD
- 用户选择的简历版本
- 用户技能和项目经历
- 公共题库
- RAG 检索到的参考问题、参考答案、评分要点和知识来源

题目类型：

- 岗位技能题
- 项目深挖题
- 场景题
- 通用基础题
- 追问题

功能要求：

- 用户从岗位池的岗位详情进入模拟面试。
- 可以生成岗位专属题库。
- 必须使用 RAG 从公共面试知识库检索候选问题、参考答案和评分要点。
- 用户可以开始、暂停和结束一次面试。
- AI 作为面试官进行多轮提问。
- AI 根据回答决定是否继续追问。
- AI 根据用户回答、参考答案、评分要点、JD 要求和简历事实进行打分。
- 结束后生成评分报告。
- 报告必须区分“事实依据”和“推测性评价”。
- 报告必须保存引用到的题库条目、用户回答和岗位/简历证据。
- 保存面试消息、使用的岗位、简历版本、模型和报告。

### 6.10 任务、日志和错误处理

需求编号：`TASK`

- 文档解析、岗位采集、岗位评测、题库生成和报告生成支持异步任务。
- 任务状态包括：等待、运行中、成功、失败、取消。
- 失败任务需要保存错误类型和可重试信息。
- 前端可以查看任务进度或最终状态。
- 系统日志需要包含请求 ID、用户 ID、任务 ID和耗时，但不能记录敏感正文。

## 7. 技术选型

### 7.1 架构方式

第一版采用前后端分离的模块化单体架构，不拆微服务：

```text
React Web
    |
Caddy / Nginx
    |
FastAPI API ---------------- PostgreSQL
    |                              |
    |                         pgvector
    |
Redis <-> Celery Worker <-> AI Provider / Job Normalizer / Object Storage
                         ^
                         |
                Browser Extension -> Boss 页面
```

选择模块化单体的理由：

- 对第一个 Agent 项目而言，开发、调试和部署成本可控。
- 业务模块仍然保持边界，后续可以把采集或 AI 任务独立部署。
- 多用户事务、岗位状态和评测记录先由一个后端统一管理，更容易保证一致性。

### 7.2 前端

- 语言：`TypeScript`
- 框架：`React + Vite`
- 组件库：`Ant Design`
- 路由：`React Router`
- 服务端状态：`TanStack Query`
- 少量客户端状态：`Zustand`，仅用于登录态、筛选条件等跨页面状态
- 表单：`React Hook Form + Zod`
- HTTP 客户端：`Axios` 或基于 `fetch` 的统一请求封装，项目内只能保留一种
- 测试：`Vitest + React Testing Library`
- 端到端测试：`Playwright`

前端职责：

- 配置中心、工作台、岗位池和模拟面试交互。
- 展示异步任务状态，轮询或使用 SSE 获取任务结果。
- 对表单做基础校验，但不承担权限判断和最终数据校验。
- API Key 只在用户提交时传输，前端不持久化完整密钥。

### 7.3 后端 API

- 语言：`Python 3.12`
- Web 框架：`FastAPI`
- 数据校验：`Pydantic v2`
- ORM：`SQLAlchemy 2.x`
- 数据库迁移：`Alembic`
- HTTP 客户端：`httpx`
- ASGI 服务器：开发使用 `Uvicorn`，生产使用多进程部署或容器副本
- 依赖管理：`uv`，使用锁文件固定依赖版本
- 代码质量：`Ruff + mypy`
- 测试：`pytest + pytest-asyncio + Testcontainers`

后端按 `auth`、`profile`、`resume`、`job`、`evaluation`、`application`、`interview`、`model_provider` 分模块。API 层只处理协议和校验，业务规则放在 service/use-case 层，数据库访问放在 repository 层。

### 7.4 数据库与检索

- 主数据库：`PostgreSQL 16`
- 向量扩展：`pgvector`
- 主键：内部使用 UUID，来源岗位额外保存来源唯一标识和岗位指纹
- 时间：数据库统一保存 UTC，前端按用户时区展示
- 半结构化 AI 结果：关键查询字段使用普通列，完整结果使用 `JSONB`

选择 PostgreSQL 的理由：

- 同时满足关系数据、JSONB 和向量检索，首版不需要引入独立向量数据库。
- 岗位、简历版本、投递状态和评测历史之间存在明确关系，关系数据库更适合。
- 支持事务和唯一约束，可以保证岗位池去重与状态流转一致性。

### 7.5 异步任务与缓存

- 消息代理和缓存：`Redis 7`
- 任务队列：`Celery 5`
- 任务范围：简历解析、浏览器采集结果标准化、AI 评测、题库生成、面试报告生成
- 任务结果：业务结果写入 PostgreSQL；Redis 只保存短期状态和缓存
- 重试策略：仅对超时、限流、临时网络错误进行指数退避重试
- 幂等：每个任务使用业务幂等键，防止用户重复点击产生重复岗位或重复报告

AI 和采集请求耗时不可控，因此不能放在普通 HTTP 请求中长时间阻塞。第一版前端使用短轮询查看任务状态，后续可切换 SSE。

### 7.6 文件存储与简历解析

- 本地开发：`MinIO`
- 生产环境：兼容 S3 的对象存储，例如阿里云 OSS、腾讯云 COS 或 AWS S3
- `.docx`：`python-docx`
- `.pdf`：`PyMuPDF`
- `.md`：`markdown-it-py`
- 文件安全：扩展名、MIME、文件头和大小共同校验

数据库只保存对象键、文件元数据和解析状态，不把二进制文件直接写入数据库。扫描型 PDF 的 OCR 不纳入第一版。

### 7.7 模型和 Agent

- 模型统一层：自定义 `ModelProvider` 协议和适配器
- OpenAI：官方 Python SDK
- Claude：Anthropic 官方 Python SDK
- 通义：DashScope SDK 或其 OpenAI 兼容接口
- DeepSeek：OpenAI 兼容接口
- 统一网络层：超时、限流、重试、Token 用量、错误归一化
- 结构化输出：`Pydantic Model + JSON Schema`
- Prompt 管理：数据库保存 Prompt 名称、版本和启用状态，代码保留默认模板
- Agent 编排：`LangGraph`
- 会话检查点：LangGraph PostgreSQL checkpointer
- 题库检索：`pgvector`
- 模拟面试 RAG：`pgvector + question_bank_items + answer_rubrics + LangGraph Tool`
- Agent 调试：节点级结构化日志；开发阶段可选接入 LangSmith

项目使用两个边界不同的 LangGraph：

1. `JobEvaluationGraph`：固定路径、可审计的岗位评测工作流。
2. `InterviewAgentGraph`：根据用户回答动态追问、换题或结束的有状态 Agent。

Boss 搜索、简历解析、模型适配器和七维分数计算本身不是 Agent。它们是图节点调用的受控工具或普通业务服务。

#### 7.7.1 Agent 设计原则

- LangGraph 只负责状态流转、节点编排、条件路由和失败恢复。
- LLM 负责语义理解、问题生成、回答分析和自然语言建议。
- 后端代码负责权限、数据读取、七维权重、Deal-breaker 封顶和数据落库。
- Agent 只能调用白名单工具，不能执行任意代码、Shell、SQL 或不受控 URL 请求。
- JD、简历和用户回答都视为不可信输入，不能覆盖 System Prompt 或改变工具权限。
- 每个节点输入和输出使用 Pydantic Model 校验。
- 每次执行保存模型、Prompt 版本、节点耗时、Token 用量和简短决策摘要。
- 不保存或向用户展示模型的隐藏思维链，只保存可解释的结论和事实依据。

#### 7.7.2 JobEvaluationGraph

用途：把一个岗位、一份简历和用户画像转化为符合评估标准的结构化报告。

状态 `JobEvaluationState` 至少包含：

```text
run_id
user_id
job_id
resume_version_id
profile_snapshot
job_snapshot
resume_snapshot
jd_analysis
gate_result
dimension_assessments
raw_weighted_score
final_score
recommendation
evidence
resume_suggestions
retry_count
errors
status
```

图节点：

```text
START
  -> load_context
  -> analyze_jd
  -> check_language_and_dealbreakers
  -> evaluate_seven_dimensions
  -> validate_evidence
       ├─ Schema/证据无效且 retry_count < 2 -> repair_assessment
       └─ 有效 -> calculate_score
  -> generate_resume_suggestions
  -> persist_evaluation
  -> END
```

节点职责：

- `load_context`：按服务端注入的 `user_id` 读取岗位、简历版本和个人画像，并生成不可变快照。
- `analyze_jd`：提取 required/preferred 技能、经验、语言、薪资、地点和工作强度信号。
- `check_language_and_dealbreakers`：使用确定性规则加结构化模型结果检查硬性条件。
- `evaluate_seven_dimensions`：按照评估框架输出七个维度的分数、状态、说明和证据。
- `validate_evidence`：检查分值范围、维度完整性、证据来源和 JSON Schema。
- `repair_assessment`：只修复缺失或非法字段，最多重试两次，不能借重试提高分数。
- `calculate_score`：由 Python 代码计算权重、推荐等级和 `≤30` 封顶，LLM 无权修改结果。
- `generate_resume_suggestions`：基于已确认的缺口给出建议，不生成虚假经历。
- `persist_evaluation`：以事务保存评测、快照、模型和 Prompt 版本。

失败规则：

- 岗位、简历或画像不存在：直接失败，不调用模型。
- 模型超时或限流：由 Celery 按规则重试。
- 两次结构修复后仍不合法：任务失败，不保存半成品评测。
- 用户重复点击：使用 `user_id + job_id + resume_version_id + framework_version` 作为幂等键。

#### 7.7.3 InterviewAgentGraph

用途：根据岗位 JD 和简历进行多轮面试，动态选择追问、下一题或结束，并生成有证据的评分报告。

状态 `InterviewState` 至少包含：

```text
session_id
user_id
job_id
resume_version_id
job_snapshot
resume_snapshot
retrieval_queries
retrieved_question_bank_items
active_rubric
interview_plan
current_question
question_history
answer_history
covered_skills
uncovered_skills
difficulty
followup_depth
question_count
max_questions
decision_summary
report
status
```

图节点：

```text
START
  -> load_interview_context
  -> analyze_interview_targets
  -> retrieve_interview_knowledge
  -> build_interview_plan
  -> select_question
  -> ask_question
  -> wait_for_user_answer (interrupt)
  -> evaluate_answer
  -> route_next_step
       ├─ follow_up -> ask_followup -> wait_for_user_answer
       ├─ next_question -> select_question
       └─ finish -> generate_interview_report
  -> persist_report
  -> END
```

节点职责：

- `load_interview_context`：加载并冻结岗位和简历版本，防止面试过程中上下文变化。
- `analyze_interview_targets`：从 JD 和简历中提取必考技能、项目风险点、经验缺口和岗位画像。
- `retrieve_interview_knowledge`：根据必考技能、岗位 JD、简历项目和上一轮回答，从公共题库检索候选问题、参考答案和评分要点。
- `build_interview_plan`：结合 JD、简历和 RAG 检索结果，确定技能题、项目题、场景题和基础题的数量、难度及覆盖目标。
- `select_question`：优先选择 RAG 检索到的高相关题目；当题库不足时，基于 JD 和简历生成专属问题，并保存生成原因。
- `ask_question`：一次只输出一个明确问题，不附带参考答案。
- `wait_for_user_answer`：使用 LangGraph interrupt 暂停，收到用户回答后从检查点继续。
- `evaluate_answer`：把用户回答与参考答案、评分要点、JD 要求和简历事实对齐，输出回答得分、事实依据、缺失点、是否需要追问和追问原因。
- `route_next_step`：根据覆盖率、回答质量、追问深度和题目数量进行条件路由。
- `generate_interview_report`：按技能、项目深度、分析能力和表达清晰度汇总报告。
- `persist_report`：保存报告以及报告引用的具体问答证据。

终止条件：

- 用户主动结束面试。
- 已达到 `max_questions`，第一版默认 8 题。
- 单个主问题最多追问 2 次。
- 已覆盖面试计划中的必考技能，且最少完成 5 个主问题。
- 会话发生不可恢复错误。

终止限制必须由代码判断，不能只依赖模型决定，防止无限循环和费用失控。

#### 7.7.4 模拟面试 RAG 设计

RAG 主要体现在 `InterviewAgentGraph`，不是单独做一个聊天机器人。它负责把“题库知识”和“岗位上下文”取出来，供 Agent 做题目选择、追问决策和答案评分。

知识库条目至少包含：

- `question_text`：题目正文。
- `question_type`：技能题、项目题、场景题、基础题或追问题。
- `skill_tags`：技能标签，例如 `Python`、`FastAPI`、`LangGraph`、`RAG`、`SQL`。
- `difficulty`：难度等级。
- `reference_answer`：参考答案或关键回答方向。
- `scoring_rubric`：评分要点、扣分点和优秀回答特征。
- `followup_suggestions`：可选追问方向。
- `source`：题目来源、版本和维护人。
- `embedding`：用于语义检索的向量。

RAG 流程：

```text
岗位 JD + 简历项目 + 已覆盖技能 + 用户上一轮回答
  -> 构造检索 Query
  -> pgvector Top-K 检索公共题库
  -> 标签、难度、题型和岗位技能二次过滤
  -> 交给 InterviewAgentGraph 选择问题或生成补充问题
  -> 用户回答
  -> 取当前题目的参考答案和评分 Rubric
  -> 对齐回答证据并打分
  -> 保存题库引用、回答引用和评分依据
```

RAG 使用边界：

- LLM 可以选择题目、生成追问和总结评价，但不能编造题库不存在的参考答案来源。
- 评分必须引用当前问题对应的 `scoring_rubric`、用户回答和 JD/简历证据。
- 如果检索结果不足，允许生成岗位专属问题，但必须标记为 `generated_from_jd_resume`。
- `pgvector` 只用于语义召回，最终权限、用户隔离、题目数量、追问上限和保存逻辑由代码控制。
- 第一版知识库源文件固定维护在 `knowledge/interview_question_bank/`，先用人工维护的 JSONL 种子数据导入 PostgreSQL，后续再做管理后台。
- 题库按岗位方向或技能域拆分，不把所有题目堆进单个大文件。
- 题库导入脚本固定为 `scripts/import_question_bank.py`，负责 JSONL 校验、可选 embedding 生成和 PostgreSQL upsert。

#### 7.7.5 Agent 工具

工具使用显式输入/输出 Schema，并由服务端注入用户身份。第一版工具包括：

| 工具 | 用途 | 是否调用 LLM |
|---|---|---:|
| `load_job_context` | 读取并校验当前用户的岗位 | 否 |
| `load_resume_context` | 读取指定简历版本 | 否 |
| `load_profile_context` | 读取求职偏好和 Deal-breakers | 否 |
| `analyze_job_description` | 结构化分析 JD | 是 |
| `retrieve_interview_knowledge` | 从公共题库检索问题、参考答案和评分要点 | 否 |
| `calculate_evaluation_score` | 计算七维加权分和封顶 | 否 |
| `save_evaluation` | 事务保存评测结果 | 否 |
| `save_interview_checkpoint` | 保存面试检查点 | 否 |
| `save_interview_report` | 保存报告和证据引用 | 否 |

工具不能接收前端传入的任意 `user_id`；当前用户必须从鉴权上下文注入。写工具必须校验幂等键和资源所有权。

#### 7.7.6 Agent 记忆与持久化

- 面试短期记忆保存在 `InterviewState`，每轮回答后写入 PostgreSQL 检查点。
- `thread_id` 使用面试 `session_id`，同一会话从最新检查点恢复。
- 用户画像、简历和岗位是长期事实来源，不让模型自行总结后永久覆盖原数据。
- 公共题库、参考答案和评分 Rubric 是 RAG 长期知识来源，面试报告只保存引用和快照，不直接修改知识库。
- 面试开始时保存岗位与简历快照，保证历史报告可复现。
- 用户删除账号或简历时，需要同步清理或匿名化相关检查点。

#### 7.7.7 Agent 可观测性和测试

每次图执行记录：

- `run_id`、`thread_id`、用户和业务资源 ID
- 节点名称、开始时间、结束时间和状态
- 模型供应商、模型名称、Prompt 版本、Token 用量和重试次数
- 条件路由结果及简短原因
- RAG 检索 Query、命中的题库条目 ID、相似度、过滤原因和最终选题原因
- Schema 校验错误和工具错误类型

测试要求：

- 节点单元测试：使用固定输入和 Mock Model 验证结构化输出。
- 路由测试：覆盖追问、下一题、主动结束、达到上限和错误结束。
- 状态恢复测试：模拟进程重启后从 PostgreSQL 检查点继续面试。
- 确定性规则测试：七维权重、语言闸门和 Deal-breaker 封顶结果不受模型影响。
- 多租户测试：Agent 工具不能读取其他用户的岗位、简历、评测和面试记录。
- 循环保护测试：任何路径都不能超过题目数、追问数和重试上限。
- RAG 测试：固定 JD 和简历时，检索结果必须命中相关技能题；低相关结果不能进入最终面试计划。

`pgvector` 第一版主要用于公共题库和岗位技能语义检索，不用于替代精确的岗位状态查询。

### 7.8 Boss 搜索采集

- 业务抽象：`JobSourceAdapter`
- 第一实现：`BossBrowserExtensionAdapter`
- 浏览器扩展：`Chrome/Edge Manifest V3 + TypeScript`
- 页面访问：扩展 Content Script 只运行在允许的 Boss 域名页面
- 通信：Web 应用与扩展通过受限消息桥通信；扩展向后端提交数据时使用单次、短期、限定采集会话的 Token
- 执行位置：页面读取发生在用户浏览器；后端 Celery 只负责标准化、校验、去重和持久化
- 数据解析：页面选择器集中管理，原始结果和后端标准字段分别经过 Schema 校验
- 去重：优先使用来源岗位 ID，其次使用公司、标题、城市和 JD 摘要生成指纹
- 稳定性：扩展心跳、单用户限速、分页上限、缓存、熔断、结构变化监控
- 权限最小化：扩展不得申请全部网站访问权限，只申请完成 Boss 页面采集所需的最小 Host Permission
- 隐私：扩展不得读取、上传或保存用户密码、Boss Cookie、聊天记录和与岗位采集无关的页面内容

重要边界：当前没有确认存在适用于本项目的公开授权岗位搜索 API，因此第一版不依赖未授权接口。Boss 页面结构、登录要求和服务条款可能变化，浏览器侧采集也不能承诺每次成功。系统不得绕过验证码、账号验证或反爬机制；采集不可用时应返回明确错误，并由管理员停用适配器，而不是写入错误数据。

### 7.9 认证和敏感数据

- 登录：邮箱密码 + JWT Access Token + Refresh Token
- 密码哈希：`Argon2id`
- API Key 加密：`AES-GCM` 或 `Fernet`，主密钥只放在生产环境变量或密钥服务
- 权限：所有 repository 查询显式带 `user_id`
- 限流：登录、模型测试、Boss 搜索和 AI 评测分别限流
- 审计：记录登录、密钥更新、岗位状态变化和简历删除等安全事件

### 7.10 本地运行、后续部署与可观测性

- 本地运行：`Docker + Docker Compose`
- 第一版本地依赖：PostgreSQL、Redis、MinIO 和后端 Worker 通过 Docker Compose 启动。
- 第一版应用：前端使用 Vite dev server，本地后端使用 Uvicorn，浏览器扩展通过开发者模式加载。
- 后续生产部署：`Docker + Docker Compose` 或轻量容器化部署。
- 后续反向代理和 HTTPS：`Caddy`，用于正式上线版本自动证书和反向代理。
- CI：`GitHub Actions` 执行静态检查、测试和镜像构建
- 日志：Python 结构化 JSON 日志，包含 request_id、user_id、task_id 和耗时
- 错误追踪：本地先使用控制台日志和结构化日志；后续上线版本接入 `Sentry`
- 指标：首版暴露健康检查和基础任务指标，后续接入 `Prometheus + Grafana`
- 数据备份：第一版不要求生产备份；后续上线版本增加 PostgreSQL 定时备份和对象存储生命周期策略

第一版验收以本地完整运行和核心流程可演示为准。生产环境至少拆分 Web、Worker、PostgreSQL、Redis 和对象存储，不能使用开发服务器直接对公网提供服务。

## 8. 推荐项目结构

```text
ai-job-AGENT/
├── backend/
│   ├── app/
│   │   ├── modules/auth/
│   │   ├── modules/profile/
│   │   ├── modules/resume/
│   │   ├── modules/job/
│   │   ├── modules/evaluation/
│   │   ├── modules/application/
│   │   ├── modules/interview/
│   │   ├── modules/model_provider/
│   │   ├── agents/
│   │   │   ├── evaluation_graph/
│   │   │   ├── interview_graph/
│   │   │   ├── tools/
│   │   │   └── shared/
│   │   └── shared/
│   ├── workers/
│   └── tests/
├── frontend/
├── browser-extension/
│   ├── src/background/
│   ├── src/content/
│   ├── src/popup/
│   └── manifest.json
├── knowledge/
│   └── evaluation_framework_cn.md
├── deploy/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

## 9. 版本迭代计划

### M0 内部工程准备（不对外发布）

任务：

- 初始化 React、FastAPI、PostgreSQL、Redis 和 Celery 工程。
- 配置 Docker Compose、Alembic、Ruff、mypy、Vitest 和 pytest。
- 实现健康检查、统一错误响应、结构化日志和 request_id。
- 建立 CI 检查和 `.env.example`。
- 完成核心数据表草案和接口契约。
- 建立 LangGraph 最小示例、统一 GraphState 约定和 PostgreSQL checkpointer 验证。
- 初始化 Chrome/Edge Manifest V3 扩展，验证 Web 页面、Content Script 与后端采集会话通信。

验收：开发者执行一条启动命令即可运行全部基础服务；数据库迁移、前后端检查和测试命令可以重复执行。

### V0.1 第一个可用版本：Boss 搜索到模拟面试闭环

任务：

- 实现邮箱密码注册登录和多用户数据隔离。
- 实现个人求职配置。
- 支持 `.docx`、`.md`、`.pdf` 简历上传、解析和默认简历。
- 实现 OpenAI、通义、DeepSeek、Claude 统一适配和连接测试。
- 实现浏览器扩展安装检测、权限检测、Boss 登录状态预检和友好引导。
- 实现由 Web 应用发起的 Boss 关键词、城市、工作形式等条件搜索。
- 使用短期采集 Token 接收扩展提交的岗位，并在后端完成字段校验和去重。
- 搜索结果展示岗位核心信息、评测状态和岗位池状态。
- 每个搜索结果提供 `AI 测评` 和 `确认投递` 两个主操作。
- AI 测评输出匹配分、分项分、依据、缺口和简历优化建议。
- 使用 `JobEvaluationGraph` 编排 JD 分析、硬性条件检查、七维评测、确定性算分和结果保存。
- 确认投递后岗位进入个人岗位池，重复搜索时显示已加入。
- 岗位池展示岗位详情、AI 评测、优化建议和投递状态。
- 岗位池提供基础模拟面试：基于 JD、简历和公共题库 RAG 检索生成专属题目，进行多轮问答，输出评分报告。
- 使用 `InterviewAgentGraph` 实现问题选择、等待回答、动态追问、条件结束和检查点恢复。
- AI、采集结果处理和文档解析使用异步任务，并展示等待、运行、部分成功、成功或失败状态。
- 评测使用 `knowledge/evaluation_framework_cn.md` 的七维权重、语言闸门和 Deal-breaker 规则。

验收：开发者在本地启动前端、后端、Worker、数据库和浏览器扩展后，一个新用户可以完成“注册 -> 上传简历 -> 配置模型 -> 搜索 Boss 岗位 -> AI 测评 -> 确认投递 -> 在岗位池查看建议 -> 完成模拟面试”的完整链路。系统不包含手动录入或 CSV 导入岗位功能。

### V0.2 简历优化和评测质量

任务：

- 支持为岗位复制专属简历版本并由用户手动编辑。
- 保存版本号、修改时间和使用的岗位。
- 支持修改前后重新评测和分数对比。
- 增加评测 Prompt 版本管理和 JSON Schema 校验失败修复流程。
- 增加评测依据引用，标识依据来自 JD 或简历的具体内容。
- 增加七维权重、总分封顶、推荐等级和信息不足标记的后端确定性计算。
- 增加 Deal-breaker、语言闸门和薪资估算的专项测试。
- 建立固定测试样本，评估不同模型输出的结构完整性和一致性。

验收：AI 不覆盖原简历；每次评测都能追踪岗位、简历版本、模型和 Prompt 版本；相同测试样本的输出结构通过自动化校验。

### V0.3 岗位池和 Boss 采集稳定性

任务：

- 完善岗位状态：待处理、准备投递、已投递、面试中、Offer、拒绝、归档。
- 记录投递时间、使用的简历版本、联系人和备注。
- 支持岗位池按状态、公司、城市和关键词筛选。
- 完善浏览器扩展心跳、采集限速、缓存、幂等、分页上限、熔断和结构变化检测。
- 增加来源岗位 ID 与岗位指纹双重去重。
- 管理端可以停用异常采集适配器并查看失败原因。
- 增加扩展版本兼容检查和强制升级提示。

验收：重复搜索不会重复创建岗位池记录；采集页面结构变化或触发验证时任务安全失败，不污染已有数据。

### V0.4 模拟面试增强

任务：

- 建立带技能标签、难度和题型的公共题库。
- 使用 JD 技能、简历项目和公共题库生成面试计划。
- 使用 LangGraph 管理提问、追问、跳题和结束状态。
- 完善面试状态快照、PostgreSQL 检查点和中断恢复。
- 增加岗位技能题、项目深挖题、场景题和基础题比例配置。
- 报告展示回答证据、技能评分、项目深度、表达情况和复习建议。
- 支持查看历史面试和同一岗位的多次报告对比。

验收：不同岗位生成的问题重点明显不同；AI 能针对用户回答进行合理追问；报告评分有对应回答作为依据。

### V0.5 安全、测试和可观测性

任务：

- 完成越权访问、API Key、文件上传和 Prompt Injection 安全测试。
- 为鉴权、岗位去重、状态流转、评测 Schema 和面试流程补充测试。
- 增加登录、模型测试、Boss 搜索和 AI 评测限流。
- 增加 Sentry、任务指标、模型耗时和 Token 用量记录。
- 增加数据库和对象存储备份、恢复演练。
- 增加隐私说明、用户数据删除和账号注销流程。

验收：核心流程自动化测试通过；用户不能访问其他用户数据；日志和错误平台不包含完整 API Key 或简历正文。

### V1.0 正式上线版本（后续）

任务：

- 配置生产域名、Caddy HTTPS 和生产环境变量。
- 将 Web、Worker、PostgreSQL、Redis 和对象存储独立运行。
- 建立 GitHub Actions 构建、测试和部署流程。
- 完成生产数据库迁移、备份和回滚方案。
- 完成 README、架构图、API 文档、部署文档和演示视频。
- 准备不包含真实个人隐私的演示账号和岗位数据。
- 对浏览器扩展权限、隐私说明和 Boss 采集方式进行上线前服务条款及合规复核。

验收：生产环境可以稳定完成 V0.1 全链路；部署失败可以回滚；数据库可以从备份恢复；Boss 采集不使用绕过验证或安全机制的方式。

## 10. 非功能需求

### 安全

- 第一版本地运行不要求 HTTPS；后续生产流量必须使用 HTTPS。
- 密码使用安全哈希。
- API Key 加密存储，日志脱敏。
- 文件类型、大小和内容进行校验。
- 所有查询强制绑定当前用户身份。
- 防止岗位 JD 和简历文本修改系统 Prompt。

### 性能

- 页面查询接口正常情况下 2 秒内返回。
- AI 长任务通过异步任务执行，不阻塞 HTTP 请求。
- 采集任务必须支持限速和最大页数。
- 大文件解析不能占满 Web 进程。

### 可维护性

- AI Prompt 单独管理并记录版本。
- 模型请求和业务逻辑分层。
- 核心评测结果必须可复现或至少可追踪。
- 所有重要状态变化有时间和操作记录。

## 11. 测试要求

- 单元测试：鉴权、数据隔离、文件校验、去重、状态流转。
- 集成测试：模型适配器、文档解析、数据库读写。
- 接口测试：注册、简历上传、岗位评测、面试会话。
- 回归测试：同一组 JD 和简历的输出结构必须符合 Schema，七维权重计算和封顶规则必须由后端测试覆盖。
- Agent 图测试：覆盖节点、条件路由、结构修复、检查点恢复、主动结束和循环上限。
- Agent 工具测试：覆盖输入 Schema、资源所有权、幂等写入和禁止跨用户访问。
- 安全测试：越权访问、密钥泄露、恶意文件和 Prompt Injection。
- 发布前手工验收完整用户流程。

## 12. 首版明确不做的事情

- 自动代投简历。
- 自动联系招聘者。
- 手动录入、粘贴 JD 或 CSV 导入岗位。
- 绕过登录、验证码或反爬机制。
- 扫描全部招聘网站并无限量采集。
- AI 自动改写并覆盖原始简历。
- 自研大模型训练和复杂推荐算法。

## 13. 项目完成的判断标准

项目不以“页面完成”作为完成标准，而以以下闭环作为核心完成标准：

```text
注册用户
  -> 配置求职意愿
  -> 上传简历
  -> 配置并测试模型
  -> 在系统内搜索 Boss 岗位
  -> 对搜索结果执行 AI 测评
  -> 查看匹配度和简历优化建议
  -> 确认投递并进入岗位池
  -> 在岗位池查看同一份评测和建议
  -> 用户创建并手动修改岗位专属简历版本
  -> 再次评测并查看分数变化
  -> 从岗位池开始岗位专属模拟面试
  -> 完成多轮模拟面试
  -> 查看评分报告
```

完成这个闭环，并达到本地运行、安全和测试要求，项目就具备比较完整的 Agent 实习作品集价值；服务器部署作为后续上线能力增强。

## 14. 待确认事项

以下问题不会阻塞 V0.1，但会影响后续产品决策：

1. 是否允许用户导出岗位专属简历为 `.docx` 或 `.pdf`？
2. 是否需要管理员后台查看任务失败和模型调用统计？
3. 后续生产环境准备使用哪家云服务，以及每月可接受的预算是多少？
