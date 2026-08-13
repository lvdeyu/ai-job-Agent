# 本地开发环境检查

检查日期：2026-08-11
最近复检：2026-08-11

## 1. 结论

当前电脑已经具备大部分基础开发工具，但在进入 `M0 本地工程骨架` 前还有两个环境点需要处理：

1. 用户自己的 PowerShell 中 Docker Desktop 已可正常输出 `docker info`，但 Codex 当前执行账户仍无法连接 Docker Engine。
2. `Python 3.12.10` 已安装在 `D:\python3.12\python.exe`，Codex 可以通过绝对路径直接使用；但 Codex 当前账户下的 `py launcher` 尚不能通过 `py -3.12` 识别它。

第一版项目不需要部署服务器，只需要本地跑通。

## 2. 已检测到的环境

| 工具 | 状态 | 版本/路径 |
|---|---|---|
| Python | 已安装 | `3.13.7`，路径 `D:\python\python.exe` |
| Python | 已安装 | `3.8`，路径 `D:\PJ\python.exe` |
| Node.js | 已安装 | `v18.20.4` |
| npm | 已安装 | `10.7.0` |
| Git | 已安装 | `2.45.1.windows.1` |
| uv | 已安装 | `0.11.12` |
| Docker CLI | 已安装 | `29.6.1` |
| Docker Compose | 已安装 | `v5.3.0` |
| Chrome | 已安装 | `C:\Program Files\Google\Chrome\Application\chrome.exe` |
| Edge | 已安装 | `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` |
| VS Code | 已安装 | `code.cmd` 可用 |

## 3. 当前阻塞项

### 3.1 Docker Engine 权限问题

用户自己的 PowerShell 已能正常执行 `docker info`，说明 Docker Desktop 本身已经可用。

但 Codex 当前执行账户仍然可以识别 Docker CLI，却无法连接 Docker Engine：

```text
permission denied while trying to connect to the docker API at npipe:////./pipe/docker_engine
```

同时 Docker 配置目录也存在访问权限问题：

```text
open C:\Users\吕德誉\.docker\config.json: Access is denied
```

Docker Desktop 进程存在，但系统服务 `com.docker.service` 处于停止状态。Codex 当前执行账户无法启动该系统服务，报错为：

```text
System error 5 has occurred.
Access is denied.
```

这说明 Docker 已经能供用户本机使用，但 Codex 当前沙箱账户还没有访问用户 Docker 配置和 Docker named pipe 的权限。后续可以先由 Codex 生成 Docker Compose 和项目文件，再由用户在自己的 PowerShell 中执行 Docker 启动命令。

### 3.2 Python 3.12 已安装，但 py launcher 视图不一致

Codex 当前账户执行 `py -0p` 的检测结果仍为：

```text
-V:3.13 *        D:\python\python.exe
-V:3.8           D:\PJ\python.exe
```

项目后端推荐 `Python 3.12`。`Python 3.13` 大概率也能跑一部分开发任务，但为了依赖兼容性和后续稳定性，建议安装 `Python 3.12.x`。

用户 PowerShell 已能看到：

```text
-V:3.12           D:\python3.12\python.exe
```

Codex 已通过绝对路径验证：

```text
D:\python3.12\python.exe --version
Python 3.12.10
```

因此后续项目可以直接使用 `D:\python3.12\python.exe` 创建虚拟环境，不阻塞开发。

## 4. 用户需要执行的最少操作

### 4.1 修复 Docker

请先打开 Docker Desktop，等待界面显示 Docker Engine 已运行。

然后在你自己的 PowerShell 中执行：

```powershell
docker info
```

如果仍然提示权限错误，请使用管理员 PowerShell 执行：

```powershell
net localgroup docker-users 吕德誉 /add
```

执行后退出当前 Windows 登录会话并重新登录，再次运行：

```powershell
docker info
```

验收标准：命令能输出 `Server` 信息，不再出现 `permission denied`。

### 4.2 Python 3.12 状态

已完成。后续 Codex 使用绝对路径 `D:\python3.12\python.exe` 即可。

## 5. 暂时不需要安装

以下工具第一版通过 Docker Compose 或项目依赖管理提供，不需要单独手动安装：

- PostgreSQL
- Redis
- MinIO
- Ruff
- pytest
- Celery
- FastAPI

## 6. 环境恢复后下一步

当 Docker 命令可以被 Codex 当前账户访问，或者用户愿意在自己的 PowerShell 中执行 Docker Compose 命令后，就可以开始 `M0 本地工程骨架`：

```powershell
docker info
D:\python3.12\python.exe --version
```

然后继续执行：

```text
初始化前端
初始化后端
配置 Docker Compose
启动 PostgreSQL + Redis + MinIO
跑通 /health
```
