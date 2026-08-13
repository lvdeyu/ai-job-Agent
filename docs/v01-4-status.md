# V0.1-4 状态记录：岗位池与搜索历史管理

更新时间：2026-08-13

## 已完成

- 搜索历史支持单条删除。
- 搜索历史支持批量选择和批量删除。
- 删除搜索历史只移除采集会话和会话-岗位关联，不删除岗位主数据、岗位池状态或已有 AI 测评。
- 后端新增批量删除 API：
  - `DELETE /api/v1/job-collections/sessions`
  - 请求体：`{"session_ids": ["..."]}`
  - 返回：`deleted_count`
- 搜索结果和搜索历史中的岗位支持 `确认投递`。
- 确认投递后岗位会标记为 `is_in_pool = true`，进入个人岗位池。
- `确认投递` 是幂等操作：重复点击不会重复创建岗位池记录。
- 后续重复搜索到同一岗位时，会继续复用同一条岗位记录，并显示已进入岗位池。
- 后端新增岗位池 API：
  - `GET /api/v1/jobs/pool`：查看当前用户岗位池。
  - `POST /api/v1/jobs/{job_id}/pool`：确认投递并加入岗位池。
- 前端左侧导航新增 `岗位池`。
- 岗位池展示岗位信息、AI 测评状态、最近一次评测摘要和简历优化建议。
- 岗位池支持重新 AI 测评。
- 岗位池支持基础筛选：岗位名、公司、城市、薪资、标签和 JD 文本。
- 岗位池中预留 `模拟面试（V0.1-5）` 入口。

## 当前实现边界

- 本阶段使用 `jobs.is_in_pool` 实现岗位池最小闭环，暂不新增投递状态表。
- 当前岗位池状态只有“已确认投递/已入池”，尚未实现待处理、已投递、面试中、Offer、拒绝、归档等完整状态流。
- 当前没有记录投递时间、联系人、备注和使用的简历版本；这些适合在 V0.3 岗位池增强里做。
- 模拟面试入口已预留，但真正的 RAG 面试流程进入 V0.1-5。

## 关键文件

- 搜索历史 API：`backend/app/api/routes/job_collections.py`
- 岗位池 API：`backend/app/api/routes/jobs.py`
- API Schema：`backend/app/schemas.py`
- 后端测试：`backend/tests/test_v01_boss_collection.py`
- 前端工作台：`frontend/src/App.tsx`
- 前端样式：`frontend/src/styles.css`

## 验证结果

```text
pytest: 24 passed
ruff: All checks passed
frontend TypeScript: passed
browser-extension TypeScript: passed
```

## 用户验收方式

1. 打开 `http://127.0.0.1:15173/`。
2. 进入 `搜索历史`。
3. 勾选多条历史记录，点击 `批量删除`，确认删除后列表应刷新。
4. 确认删除历史不会删除岗位池或已有 AI 测评。
5. 进入 `岗位搜索` 或展开某条搜索历史。
6. 对岗位点击 `确认投递`。
7. 进入左侧 `岗位池`，确认该岗位出现，并可继续查看 AI 测评和建议。
8. 在岗位池筛选框输入岗位名、公司或城市，确认列表能正确过滤。

## 下一步

用户确认 V0.1-4 后，进入 `V0.1-5 模拟面试与 RAG`：

- 创建题库数据表。
- 导入 `knowledge/interview_question_bank/seeds/*.jsonl`。
- 实现题库检索。
- 从岗位池进入模拟面试。
- 基于 JD、简历、评测结果和题库生成专属问题。
- 保存并展示面试评分报告。
