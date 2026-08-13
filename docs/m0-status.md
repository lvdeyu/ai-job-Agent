# M0 本地工程骨架状态

更新日期：2026-08-11

## 已完成

- 已创建后端工程骨架：`backend/`
- 已创建前端工程骨架：`frontend/`
- 已创建浏览器扩展骨架：`browser-extension/`
- 已创建本地依赖配置：`infra/docker-compose.yml`
- 已创建后端健康检查接口：`GET /health`
- 已创建 Alembic 迁移骨架和 M0 baseline migration
- 已配置后端 `pytest`、`ruff`
- 已配置前端 `React + TypeScript + Vite + Ant Design`
- 已配置浏览器扩展 Manifest V3 最小骨架
- 已创建本地依赖启动脚本：`scripts/start_local_deps.ps1`
- 已创建 M0 检查脚本：`scripts/check_m0.ps1`

## 已验证

后端测试：

```text
1 passed in 0.34s
```

后端 Ruff：

```text
All checks passed!
```

后端真实健康检查：

```json
{"status":"ok","app_name":"ai-job-AGENT","environment":"local"}
```

Alembic 离线迁移 SQL：

```text
CREATE EXTENSION IF NOT EXISTS vector;
```

题库校验：

```text
题库校验通过：3 道题
覆盖方向：agent_development_intern
题型：project_deep_dive, skill
当前为 dry-run：未写入数据库，未调用 embedding 接口
```

前端构建：

```text
✓ built
```

浏览器扩展构建：

```text
browser-extension/dist/background.js
browser-extension/dist/content.js
browser-extension/dist/manifest.json
```

Docker Compose 配置语法：

```text
docker compose -f infra/docker-compose.yml config
```

已通过配置展开检查。

## Docker 依赖启动记录

用户已在自己的 PowerShell 中执行：

```powershell
cd D:\Users\codex\workspace\ai-job-AGENT
powershell -ExecutionPolicy Bypass -File .\scripts\start_local_deps.ps1
```

启动结果：

- `ai-job-agent-postgres` 已启动
- `ai-job-agent-redis` 已启动
- `ai-job-agent-minio` 已启动

说明：Codex 当前沙箱账户仍无法直接访问 Docker named pipe：

```text
permission denied while trying to connect to the docker API at npipe:////./pipe/docker_engine
```

但容器已经通过用户本机 PowerShell 成功启动，并且 Codex 可以通过 localhost 端口访问这些服务。

## 最近端口复检

Codex 已从 `localhost` 端口侧复检本地依赖是否已经启动。结果如下：

| 服务 | 端口 | 结果 |
|---|---:|---|
| PostgreSQL | 5432 | 已连通 |
| Redis | 6379 | 已连通 |
| MinIO API | 9000 | 已连通 |
| MinIO Console | 9001 | 已连通 |

## 完整 M0 检查结果

已执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_m0.ps1
```

结果摘要：

```text
PostgreSQL port 5432 OK
Redis port 6379 OK
MinIO API port 9000 OK
MinIO Console port 9001 OK
题库校验通过：3 道题
1 passed in 0.33s
All checks passed!
pgvector=0.8.6; alembic=20260811_0001
Redis PING OK
MinIO health OK
frontend npm run build: built
browser-extension npm run build: success
M0 local checks finished.
```

备注：前端构建中出现 Ant Design 依赖的 `"use client"` 打包警告和 chunk size 警告，但构建成功，M0 阶段不阻塞。

## 当前结论

M0 工程骨架已经完成。后端、前端、扩展、迁移、题库校验、PostgreSQL、Redis、MinIO 和 pgvector 均已完成本地验证，可以进入 `V0.1-1 账户、配置中心、简历上传`。
