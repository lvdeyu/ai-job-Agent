# V0.1-6 状态记录：本地联调和收尾

更新时间：2026-08-13

## 已完成

- 串联前端完整流程入口：
  - 基础配置。
  - 岗位搜索。
  - 搜索历史。
  - 岗位池。
  - 模拟面试。
  - 面试历史。
  - 任务状态。
- 统一后端接口错误响应：
  - 返回 `error.code`。
  - 返回 `error.message`。
  - 返回 `error.request_id`。
  - 参数校验错误返回 `VALIDATION_ERROR` 和 `details`。
- 增加请求级 `request_id`：
  - 支持读取请求头 `X-Request-ID`。
  - 未传入时自动生成。
  - 响应头返回 `X-Request-ID`。
- 增加结构化 JSON 访问日志：
  - `request_id`。
  - `method`。
  - `path`。
  - `status_code`。
  - `duration_ms`。
- 前端错误提示兼容统一错误响应，会展示后端返回的错误消息和 `request_id`。
- 新增任务状态接口：
  - `GET /api/v1/tasks/status`
  - 展示本地任务执行器状态。
  - 展示 Celery 队列未启用状态。
  - 展示最近 Boss 采集状态。
  - 展示最近模拟面试状态。
- 前端左侧新增 `任务状态` 功能点。
- 补充基础测试：
  - 注册登录。
  - 简历解析。
  - 模型连接测试。
  - 题库导入。
  - 岗位去重。
  - 评测 Schema。
  - 面试状态流转。
  - 统一错误响应和任务状态。
- README 当前阶段已更新为 `V0.1 本地闭环`。

## 当前实现边界

- V0.1 本地版本没有启动真实 Celery worker；任务状态页明确展示 `Celery 异步队列：未启用`。
- Boss 采集仍依赖浏览器扩展主动回传，不做后台自动爬取。
- 真实外部 embedding、PostgreSQL `vector` 列和 LangGraph 原生 checkpoint store 留到后续增强；当前本地闭环使用确定性 embedding fallback 和数据库会话快照。

## 关键文件

- 应用入口：`backend/app/main.py`
- 观测与错误处理：`backend/app/core/observability.py`
- 任务状态 API：`backend/app/api/routes/tasks.py`
- API Schema：`backend/app/schemas.py`
- 后端收尾测试：`backend/tests/test_v01_local_polish.py`
- 前端工作台：`frontend/src/App.tsx`
- 前端样式：`frontend/src/styles.css`

## 验证结果

后端：

```text
pytest: 36 passed
ruff: All checks passed
```

前端：

```text
TypeScript: passed
```

浏览器扩展：

```text
TypeScript: passed
```

## 本地最终验收路径

1. 启动本地依赖：`.\scripts\start_local_deps.ps1`
2. 启动后端：`http://127.0.0.1:18000`
3. 启动前端：`http://127.0.0.1:15173`
4. 加载浏览器扩展：`browser-extension/dist`
5. 注册登录。
6. 上传默认简历。
7. 配置 AI 模型。
8. 搜索 Boss 岗位。
9. 对岗位执行 AI 测评。
10. 确认投递进入岗位池。
11. 从岗位池开始模拟面试。
12. 提交回答并生成报告。
13. 在面试历史查看报告。
14. 在任务状态查看本地执行器、Celery 队列状态、最近采集和最近面试。
