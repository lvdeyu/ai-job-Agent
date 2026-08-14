# V0.2 状态记录：简历优化和评测质量

更新时间：2026-08-14

## 已完成

- 支持在岗位池为单个岗位上传简历：
  - 用户可以在 WPS 或 Word 中自行修改简历后回到岗位池上传。
  - 上传入口是岗位卡片内的按钮，点击后弹出支持拖拽和选择文件的上传弹窗。
  - 支持 `.docx`、`.md`、文本型 `.pdf`，沿用统一解析和大小限制。
- 支持岗位简历优先评测：
  - `POST /api/v1/resumes/jobs/{job_id}/upload` 会生成 `source_type=job_upload` 的岗位级简历版本。
  - AI 测评不传 `resume_version_id` 时，后端优先使用该岗位最新上传的简历。
  - 岗位没有上传简历时，后端自动回退基础配置里的默认简历。
  - 岗位级上传不会覆盖默认简历，也不会出现在基础配置的默认简历列表中。
- 支持评测来源追踪：
  - 每条评测记录保存实际使用的简历版本、模型配置、评估框架版本、Prompt 版本和输出 Schema 版本。
  - 评测响应返回 `resume_source_type`，前端展示“岗位上传简历 / 默认简历”等来源。
  - 评测证据中明确写入本次使用的简历版本。
- 岗位池前端新增轻量简历面板：
  - 显示当前将使用岗位上传简历还是默认简历。
  - 支持上传或更换岗位简历。
  - 点击 AI 测评时自动按后端优先级选择简历。
  - 展示最新评测相对上一次评测的总分变化、七维分差和推荐等级变化。
- 模拟面试入口同样在未指定版本时优先使用岗位上传简历。
- 补充 V0.2 后端测试：
  - 岗位池上传简历。
  - 岗位上传简历优先于默认简历参与评测。
  - 岗位上传简历不覆盖默认简历。
  - 非岗位池岗位和跨用户岗位不能上传岗位简历。
  - 保留岗位专属版本复制、只读保护和指定版本复评的兼容测试。
  - 多用户隔离。

## 当前实现边界

- V0.2 仍使用 `local-rule-v1` 规则评测，没有接入真实 LLM 结构修复流程。
- 旧的岗位专属文本编辑器已从主流程移除；用户在 WPS 或 Word 中完成简历编辑，本系统负责上传、解析、评测和追踪。
- 岗位级上传文件当前仍复用 `resume_files` 存储表，通过 `resume_versions.source_type/job_id` 与基础默认简历区分。
- 岗位池状态、投递时间、联系人和备注仍留到 `V0.3`。
- 真实 Celery Worker、真实 embedding、`pgvector` 专用列和 LangGraph 原生 checkpoint 仍留到后续版本。

## 关键文件

- 简历模型：`backend/app/models/resume.py`
- 评测模型：`backend/app/models/job_evaluation.py`
- 数据库迁移：`backend/alembic/versions/20260813_0008_v02_resume_versions.py`
- 简历 API：`backend/app/api/routes/resumes.py`
- 评测 API：`backend/app/api/routes/jobs.py`
- 评测服务：`backend/app/services/job_evaluation.py`
- API Schema：`backend/app/schemas.py`
- 后端测试：`backend/tests/test_v02_resume_versions.py`
- 前端工作台：`frontend/src/App.tsx`
- 前端样式：`frontend/src/styles.css`

## 验证结果

后端：

```text
pytest: 41 passed
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

## 用户验收方式

1. 启动本地依赖：`.\scripts\start_local_deps.ps1`
2. 启动后端：`http://127.0.0.1:18000`
3. 启动前端：`http://127.0.0.1:15173`
4. 注册或登录。
5. 上传默认简历。
6. 采集岗位并点击 `确认投递` 加入岗位池。
7. 在岗位池找到该岗位，点击 `上传简历`。
8. 在弹窗中拖拽或选择 WPS/Word 修改后的简历，点击 `上传并解析`。
9. 点击 `用岗位简历复评`。
10. 查看 AI 测评结果、测评简历来源、输出 Schema 版本、“较上次”总分变化、七维分差和推荐等级变化。
11. 点击 `开始模拟面试`，确认面试默认使用该岗位上传的简历。

## 下一步

进入 `V0.3 岗位池和 Boss 采集稳定性`：

- 完善岗位池状态流转。
- 增加投递时间、使用简历版本、联系人和备注。
- 强化岗位池筛选。
- 完善 Boss 扩展心跳、限速、幂等、分页上限和结构变化检测。
- 增加来源岗位 ID 与岗位指纹双重去重。
