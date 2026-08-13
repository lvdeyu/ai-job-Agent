# V0.2 状态记录：简历优化和评测质量

更新时间：2026-08-13

## 已完成

- 支持为岗位池中的岗位复制岗位专属简历版本：
  - 默认从当前选中的简历版本复制。
  - 未选择时从默认简历最新版本复制。
  - 保存来源版本、关联岗位、版本号、创建时间和更新时间。
- 支持手动编辑岗位专属简历版本：
  - 原始上传版本只读，不允许覆盖。
  - 岗位专属版本可编辑标题和正文。
  - 保存后更新时间会变化。
- 支持使用指定简历版本重新评测岗位：
  - 评测请求可传入 `resume_version_id`。
  - 每条评测记录保存岗位、简历版本、模型配置、评估框架版本、Prompt 版本和输出 Schema 版本。
  - 评测证据中明确写入本次使用的简历版本。
- 岗位池前端新增岗位专属简历面板：
  - 选择默认或岗位专属简历版本。
  - 复制岗位专属版本。
  - 手动编辑并保存版本。
  - 用选中版本重新 AI 测评。
  - 展示最新评测相对上一次评测的总分变化、七维分差和推荐等级变化。
- 模拟面试入口会使用岗位池中当前选中的简历版本。
- 补充 V0.2 后端测试：
  - 岗位专属简历复制。
  - 原始版本只读保护。
  - 手动编辑后重新评测。
  - 修改前后分数对比。
  - 多用户隔离。

## 当前实现边界

- V0.2 仍使用 `local-rule-v1` 规则评测，没有接入真实 LLM 结构修复流程。
- 前端简历编辑为文本编辑，暂未做富文本、`.docx` 导出或差异高亮。
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
pytest: 39 passed
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
7. 在岗位池找到该岗位，点击 `复制岗位专属版本`。
8. 修改岗位专属简历标题和正文，点击 `保存手动修改`。
9. 点击 `用该版本复评`。
10. 查看 AI 测评结果、简历版本、输出 Schema 版本、“较上次”总分变化、七维分差和推荐等级变化。
11. 点击 `开始模拟面试`，确认面试使用当前选中的简历版本。

## 下一步

进入 `V0.3 岗位池和 Boss 采集稳定性`：

- 完善岗位池状态流转。
- 增加投递时间、使用简历版本、联系人和备注。
- 强化岗位池筛选。
- 完善 Boss 扩展心跳、限速、幂等、分页上限和结构变化检测。
- 增加来源岗位 ID 与岗位指纹双重去重。
