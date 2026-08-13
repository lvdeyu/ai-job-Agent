# V0.1-1 状态记录：账户、配置中心、简历上传

更新时间：2026-08-12

## 已完成

- 后端注册、登录、当前用户接口：
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/me`
- 本地 JWT 鉴权和密码哈希。
- 用户数据隔离基础能力：简历、个人配置、模型配置查询都绑定当前 `user_id`。
- 个人求职配置：
  - 意愿岗位
  - 薪资范围
  - 工作城市
  - 实习/全职
  - 不接受条件
- AI 模型供应商配置：
  - OpenAI
  - 通义千问
  - DeepSeek
  - Claude
  - API Key、模型名、Base URL、超时时间
- AI 连接测试：
  - 真实供应商请求路径已预留。
  - `sk-local-test` 开头的 Key 用于本地无外网/无真实 Key 的开发自测。
- 简历上传和文本抽取：
  - `.md`
  - `.docx`
  - 文本型 `.pdf`
  - 扫描版 PDF 暂不支持 OCR。
- 默认简历逻辑：用户第一份上传的简历自动设为默认简历。
- 最小前端配置中心页面：
  - 注册/登录
  - 保存个人配置
  - 保存并测试 AI 配置
  - 上传并查看简历

## 关键文件

- 后端入口：[backend/app/main.py](../backend/app/main.py)
- 鉴权工具：[backend/app/core/security.py](../backend/app/core/security.py)
- 数据模型：[backend/app/models](../backend/app/models)
- API 路由：[backend/app/api/routes](../backend/app/api/routes)
- 简历解析：[backend/app/services/resume_parser.py](../backend/app/services/resume_parser.py)
- 模型连接测试：[backend/app/services/model_connection.py](../backend/app/services/model_connection.py)
- 数据库迁移：[backend/alembic/versions/20260811_0002_v01_account_config_resume.py](../backend/alembic/versions/20260811_0002_v01_account_config_resume.py)
- 前端页面：[frontend/src/App.tsx](../frontend/src/App.tsx)

## 验证结果

后端：

```text
ruff: All checks passed
pytest: 3 passed
alembic: 20260811_0001 -> 20260811_0002 migrated successfully
```

前端：

```text
TypeScript: passed
Vite build: passed with temporary output directory ../tmp/frontend-build-v01
```

说明：当前 Windows 环境里的 `frontend/dist` 旧文件存在写入/删除权限限制，所以验证构建输出到了 `tmp` 目录。代码本身可以正常打包。

## 还没做

- Boss 浏览器扩展采集。
- 岗位列表、岗位池、AI 岗位评测。
- 模拟面试和 RAG。
- API Key 加密保存。

其中 API Key 加密保存建议放到 V0.1-6 或上线准备前处理；当前第一版只本地运行，不提交真实密钥到代码即可。
