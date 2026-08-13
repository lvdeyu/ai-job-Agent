# V0.1-2 状态记录：Boss 浏览器扩展采集

更新时间：2026-08-12

## 已完成

- 本地 Git 仓库已初始化。
- 后端 Boss 采集基础链路：
  - 创建采集会话。
  - 签发短期 `collection_token`。
  - 生成 Boss 搜索 URL。
  - 接收浏览器扩展提交的岗位批次。
  - 按当前用户 `user_id` 保存岗位。
  - 使用岗位指纹做用户内去重。
  - 查询当前用户岗位列表。
- 浏览器扩展增强采集：
  - Manifest V3 扩展。
  - Web 页面扩展检测。
  - Web 与扩展通过 `window.postMessage` + content script 桥接。
  - 扩展打开或复用 Boss 搜索页。
  - Content Script 读取当前 Boss 页面可见岗位卡片。
  - 扩展提交采集结果到后端。
  - 不申请 `cookies` 权限。
  - 不读取或上传 Boss 密码、Cookie、聊天记录。
- 采集异常提示：
  - 未检测到扩展。
  - Boss 未登录或登录失效。
  - Boss 出现验证码或安全验证。
  - 页面结构无法识别。
  - 搜索无有效结果。
- 前端工作台：
  - 左侧功能栏布局：
    - 基础配置
    - 岗位搜索
    - 岗位池入口预留到 `V0.1-4`
  - Boss 采集前准备说明。
  - 扩展重新检测按钮。
  - 岗位关键词、城市、工作形式、采集数量表单；关键词默认空，避免刷新后重复清理旧关键词。
  - 默认采集 `20` 个岗位，可选 `10/20/50`。
  - 采集状态展示。
  - 岗位搜索结果列表展示。
  - 采集完成后展示新增、重复、过滤的不相关岗位数量。
  - 预留 `AI 测评（V0.1-3）` 和 `确认投递（V0.1-4）` 按钮入口，当前禁用。
- 岗位相关性过滤：
  - Boss 搜索 URL 只使用用户输入的岗位关键词和城市，不再把“实习/全职”拼进搜索关键词。
  - 工作形式作为独立筛选条件：岗位采集回来后，后端再根据标题、标签、薪资、经验和描述判断是否符合实习/全职。
  - 后端保存前会按用户搜索关键词过滤明显不相关岗位；`Agent/AI` 会保留同义表达，`Java/Python` 这类技术关键词会更严格，避免只因 JD 偶然提到一次就进入结果。
  - 例如搜索 `python` 时，不再保存标题、标签和卡片文本都不包含 `python` 的机械设计、泛应届类岗位。
  - 例如搜索 `java` 时，不再保存标题和标签都偏 `Agent/RAG/LLM`、只在 JD 里偶然提到一次 `Java` 的 AI 岗位。
  - 全部结果都不相关时返回可理解提示，而不是把脏岗位写入岗位列表。
- 搜索状态隔离：
  - 每次开始采集或清空条件都会清空本次采集结果和测评缓存。
  - 扩展复用 Boss 标签页时，会等待 URL、城市、搜索框关键词都切到本次搜索后再读取岗位卡片。
  - 如果 Boss 页面还停留在旧关键词，会返回 `PAGE_NOT_READY`，提示用户稍等页面加载后重试。
- README 已补充扩展安装和 Boss 采集前准备步骤。

## 关键文件

- 后端采集路由：[backend/app/api/routes/job_collections.py](../backend/app/api/routes/job_collections.py)
- 后端岗位路由：[backend/app/api/routes/jobs.py](../backend/app/api/routes/jobs.py)
- 岗位数据模型：[backend/app/models/job_collection.py](../backend/app/models/job_collection.py)
- Boss 搜索 URL 构建：[backend/app/services/boss_search.py](../backend/app/services/boss_search.py)
- Boss 采集迁移：[backend/alembic/versions/20260812_0003_v01_boss_collection.py](../backend/alembic/versions/20260812_0003_v01_boss_collection.py)
- 前端工作台：[frontend/src/App.tsx](../frontend/src/App.tsx)
- 前端样式：[frontend/src/styles.css](../frontend/src/styles.css)
- 扩展 Manifest：[browser-extension/manifest.json](../browser-extension/manifest.json)
- 扩展后台脚本：[browser-extension/src/background.ts](../browser-extension/src/background.ts)
- 扩展页面脚本：[browser-extension/src/content.ts](../browser-extension/src/content.ts)
- 扩展类型声明：[browser-extension/src/chrome.d.ts](../browser-extension/src/chrome.d.ts)

## 本地测试步骤

1. 启动后端和前端：

```text
后端：http://127.0.0.1:18000
前端：http://127.0.0.1:15173
```

2. 构建扩展：

```powershell
cd browser-extension
npm run build
```

3. 在 Chrome/Edge 扩展管理页开启开发者模式，加载：

```text
D:\Users\codex\workspace\ai-job-AGENT\browser-extension\dist
```

4. 在同一个浏览器登录 Boss 直聘。

5. 回到 ai-job-AGENT 工作台，点击“重新检测扩展”。

6. 输入岗位关键词、城市、工作形式和采集数量，点击“开始采集 Boss 岗位”。

## 验证结果

后端：

```text
pytest: 8 passed
ruff: All checks passed
health: http://127.0.0.1:18000/health OK
```

前端：

```text
TypeScript: passed
Vite build: passed with temporary output directory ../tmp/frontend-build-v012-ux
dev server: http://127.0.0.1:15173 OK
```

浏览器扩展：

```text
TypeScript: passed
npm run build: passed
dist/background.js generated
dist/content.js generated
dist/manifest.json generated
dist/content.js no export syntax
dist/background.js no export syntax
```

说明：扩展构建第一次在默认沙箱内写入 `browser-extension/dist` 失败，提升权限后构建成功。原因是当前运行环境对已有 dist 文件写入有限制，不是扩展代码类型错误。

修复记录：Chrome Manifest V3 的 content script 不能包含顶层 `export {}`。之前为了规避 TypeScript 全局类型重名，构建产物里出现了 `export {};`，导致 Chrome 无法注入 `content.js`，前端检测不到扩展。当前已改为 IIFE 作用域隔离，构建产物不再包含 `export`。

## 当前限制

- 第一版只采集 Boss 页面当前可见岗位，不做自动翻页和无限滚动。
- 不绕过 Boss 登录、验证码、安全验证或其他风控。
- Boss 页面结构变化时可能返回 `SOURCE_CHANGED`，需要更新选择器。
- 当前采集会先读取页面列表卡片，再顺序打开岗位详情页补全 JD、薪资、城市、经验和学历等字段；默认最多对前 20 个岗位做详情补全。
- Boss 搜索 URL 已从旧的 `jobType=intern` 参数改为更稳的关键词策略：只搜索用户输入的关键词，城市会转换为已知 Boss 城市 code，例如 `济南 -> 101120100`；工作形式不拼进关键词。
- `AI 测评` 已在 `V0.1-3` 启用；`确认投递` 按钮仍属于 `V0.1-4`，当前禁用。
- Git 仓库刚初始化，尚未创建第一次提交。

## 下一步

V0.1-2 已进入后续迭代，当前重点转向 V0.1-3/V0.1-4：

- 如果扩展检测失败，优先检查是否加载了 `browser-extension/dist`，以及当前页面是否为 `http://127.0.0.1:15173`。
- 如果 Boss 采集失败，优先根据页面提示处理登录、验证码或页面结构问题。
- `V0.1-3 岗位 AI 测评` 已完成基础可用链路，详见 `docs/v01-3-status.md`。

