# Boss 浏览器侧采集设计

## 1. 结论

截至 2026-08-11，项目没有确认到一个面向普通第三方应用、允许公开申请并用于求职岗位搜索的 Boss 官方授权 API。因此第一版不依赖第三方抓包接口或未授权 API，采用用户浏览器侧采集。

第一版明确不做公开网页搜索、搜索引擎抓取或手动导入作为降级方案。Boss 搜索能力只通过浏览器扩展增强采集提供；扩展不可用、用户未登录或出现验证码时，系统返回明确提示并等待用户处理。

如果后续获得 Boss 官方书面授权和接口文档，应新增 `BossOfficialApiAdapter`，并优先使用官方 API；浏览器扩展保留为可停用适配器。

## 2. 方案目标

- 用户在 ai-job-AGENT 中填写搜索条件。
- 使用用户自己的浏览器和 Boss 登录状态访问岗位页面。
- 扩展只读取本次搜索页面中用户可见的岗位数据。
- 不要求用户手动复制 JD 或导入 CSV。
- 不读取或上传 Boss 密码、Cookie、聊天记录。
- 遇到登录、验证码或安全验证时暂停，等待用户手动处理。

## 3. 架构

```text
ai-job-AGENT Web
    |
    | 创建短期采集会话
    v
FastAPI <---- 岗位批次 ---- Browser Extension
    |                            |
    |                            v
    |                       Boss 搜索页面
    v
Celery Job Normalizer
    |
    v
字段校验 -> 去重 -> PostgreSQL -> 工作台
```

组件职责：

- Web：收集搜索条件、检测扩展、展示预检和采集进度。
- Browser Extension：在用户浏览器中打开或复用 Boss 页面，读取可见岗位。
- FastAPI：创建采集会话、签发短期 Token、接收批次数据。
- Celery：清洗字段、生成指纹、去重和持久化。
- PostgreSQL：保存采集会话、标准岗位和失败原因。

## 4. 用户首次准备

1. 安装 Chrome/Edge Manifest V3 扩展。
2. 授予扩展访问 Boss 页面所需的最小权限。
3. 在同一浏览器中打开 Boss 并手动登录。
4. 返回 ai-job-AGENT，点击“重新检测”。

安装完成后，系统显示：

```text
扩展已连接
Boss 登录状态：已就绪
默认采集数量：20
```

系统不得要求用户向 ai-job-AGENT 输入 Boss 密码。

## 5. 每次搜索流程

```text
填写关键词和筛选条件
  -> 检测扩展心跳
  -> 检查扩展权限
  -> 创建短期采集会话
  -> 扩展打开 Boss 搜索页面
  -> 检查登录/验证码
  -> 分批读取当前可见岗位
  -> 后端校验和去重
  -> 返回工作台
```

默认值：

- 默认目标岗位数：20
- 可选数量：10、20、50
- 单次硬上限：50
- 默认最多处理 3 页
- 批次大小：10
- 采集会话 Token 建议有效期：10 分钟

实际结果可能少于目标数量。页面没有更多岗位、触发验证、用户取消或页面结构变化时，允许返回 `PARTIAL_SUCCESS`。

## 6. 扩展通信和安全

- 扩展使用 Manifest V3。
- Content Script 只允许在配置的 Boss 域名运行。
- 不申请 `cookies` 权限。
- 不申请访问所有网站的权限。
- Web 与扩展通信必须校验来源域名和消息 Schema。
- 后端签发一次性采集 Token，只允许向指定 `collection_session_id` 上传岗位。
- Token 过期、会话完成或取消后立即失效。
- 后端从 Token 注入 `user_id`，不信任扩展提交的用户 ID。
- 每批岗位限制数量和请求体大小。
- 原始 HTML 不直接保存；只提交业务需要的结构化字段和必要文本。

## 7. 后端接口草案

```text
POST /api/v1/job-collections
GET  /api/v1/job-collections/{session_id}
POST /api/v1/job-collections/{session_id}/heartbeat
POST /api/v1/job-collections/{session_id}/batches
POST /api/v1/job-collections/{session_id}/complete
POST /api/v1/job-collections/{session_id}/cancel
```

创建采集会话请求：

```json
{
  "source": "boss",
  "keyword": "Agent 开发",
  "city": "上海",
  "employment_type": "internship",
  "target_count": 20
}
```

批次上传只接受后端定义的岗位 Schema。缺少标题、公司、来源链接或 JD 等关键字段时，整条岗位进入拒绝记录，不进入正式岗位表。

## 8. 状态和恢复

| 状态 | 含义 | 恢复方式 |
|---|---|---|
| `EXTENSION_REQUIRED` | 未检测到扩展 | 安装后重新检测 |
| `PERMISSION_REQUIRED` | 缺少页面权限 | 用户手动授权 |
| `AUTH_REQUIRED` | Boss 未登录 | 用户在 Boss 页面登录 |
| `CAPTCHA_REQUIRED` | Boss 要求验证 | 用户手动完成验证 |
| `RUNNING` | 正在采集 | 保持页面开启 |
| `PARTIAL_SUCCESS` | 只获得部分岗位 | 查看已有结果或稍后重试 |
| `RATE_LIMITED` | 访问频率受限 | 到提示时间后重试 |
| `SOURCE_CHANGED` | 页面结构无法识别 | 停用适配器并更新选择器 |
| `SUCCESS` | 采集完成 | 进入工作台 |
| `FAILED` | 其他失败 | 查看原因并重新开始 |

登录或验证码处理完成后，不复用已经过期的采集会话，前端重新执行预检并创建新会话。已经成功写入的岗位通过指纹去重，不会重复创建。

## 9. 用户提示原则

- 提示必须说明发生了什么、为什么停止、用户下一步做什么。
- 不能只显示“请求失败”或技术异常堆栈。
- 登录提示必须明确“系统不会读取或保存你的密码”。
- 验证码提示必须明确“系统不会尝试绕过验证”。
- 部分成功必须显示“已采集数量/目标数量”。
- 搜索成功但零结果必须与采集失败使用不同状态和文案。

## 10. 验收标准

- 未安装扩展时，用户能看到安装步骤而不是空白搜索结果。
- 未登录 Boss 时，系统能引导用户到 Boss 页面完成登录。
- 扩展不读取或上传密码和 Cookie。
- 默认采集 20 个岗位，且不能超过用户选择的数量和系统硬上限。
- 采集结果经过 Schema 校验和岗位指纹去重。
- 遇到验证码时暂停，不绕过验证。
- 页面结构变化时返回 `SOURCE_CHANGED`，不保存错误岗位。
- 部分成功时保存合法岗位，并显示实际数量和失败原因。
- 用户 A 的采集 Token 不能向用户 B 的采集会话提交数据。
