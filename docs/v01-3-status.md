# V0.1-3 状态记录：岗位 AI 测评

更新时间：2026-08-12

## 已完成

- 后端新增岗位评测数据模型 `JobEvaluation`。
- 新增数据库迁移 `20260812_0005_v01_job_evaluations.py`，本地数据库已升级到 `20260812_0005 (head)`。
- 新增评测 API：
  - `POST /api/v1/jobs/{job_id}/evaluations`：基于当前用户岗位、默认简历和个人配置生成评测。
  - `GET /api/v1/jobs/{job_id}/evaluations`：查看该岗位历史评测记录。
- 评测结果按 `knowledge/evaluation_framework_cn.md` 固定七维框架输出：
  - 技能匹配 30%。
  - 经验匹配 25%。
  - 行为文化 15%。
  - 薪资结构 10%。
  - 工作强度 10%。
  - 稳定性与合规 5%。
  - 通勤与城市 5%。
- 后端确定性计算：
  - 计算原始加权分。
  - Deal-breaker 或语言闸门命中时，总分封顶到不高于 30。
  - 信息不足维度使用 `insufficient_data` 标记并按中性分处理。
- 评测报告保存：
  - 总分、建议等级、一句话理由。
  - 七维分项分、权重、解释和信息状态。
  - 亮点、风险缺口、薪资依据、证据、简历优化建议、诚实缺口说明。
  - 使用的简历版本、模型配置 ID、框架版本和 prompt 版本。
- 前端岗位搜索结果页启用 `AI 测评` 按钮。
- 前端展示岗位评测摘要：匹配度、建议等级、分项维度、风险缺口、简历建议和使用的简历版本。
- 前端支持重复点击“重新 AI 测评”，并自动加载该岗位最近一次评测。

## 当前实现边界

- 本切片先实现规则版 `local-rule-v1` 评测，确保评分框架、数据结构、保存和展示闭环稳定。
- 当前没有让 LLM 直接决定总分；后端规则负责权重、封顶和信息不足处理。
- 下一步接入 `JobEvaluationGraph` 时，LLM 适合负责 JD 结构化、解释和建议补充，但总分仍必须由后端确定性规则校验。
- 当前评测依赖默认简历；如果用户没有上传或设置默认简历，会返回清晰错误。

## 关键文件

- 评测模型：`backend/app/models/job_evaluation.py`
- 评测迁移：`backend/alembic/versions/20260812_0005_v01_job_evaluations.py`
- 评测服务：`backend/app/services/job_evaluation.py`
- 岗位评测 API：`backend/app/api/routes/jobs.py`
- API Schema：`backend/app/schemas.py`
- 后端测试：`backend/tests/test_v01_job_evaluation.py`
- 前端工作台：`frontend/src/App.tsx`
- 前端样式：`frontend/src/styles.css`

## 验证结果

```text
pytest: 15 passed
ruff: All checks passed
frontend TypeScript: passed
browser-extension TypeScript: passed
alembic current: 20260812_0005 (head)
backend health: http://127.0.0.1:18000/health OK
frontend: http://127.0.0.1:15173 OK
```

## 用户验收方式

1. 打开 `http://127.0.0.1:15173/`。
2. 确认已经上传默认简历。
3. 搜索并采集 Boss 岗位。
4. 在岗位搜索结果中点击 `AI 测评`。
5. 查看岗位卡片下方是否展示匹配度、建议等级、风险缺口和简历建议。

## 下一步

进入 `V0.1-4 岗位池`：

- 搜索结果支持 `确认投递`。
- 已确认岗位进入岗位池。
- 后续搜索时标记或过滤已进入岗位池。
- 岗位池可查看同一份 AI 评测和建议。
