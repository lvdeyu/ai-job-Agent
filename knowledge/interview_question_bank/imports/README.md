# 外部题库导入暂存区

本目录用于临时放置从课程笔记、面经、个人总结中整理出来的题库素材。

## 子目录

- `raw/`：原始资料区，允许格式松散，不直接导入数据库。
- `processed/`：处理中间稿区，保存抽取文本、候选题和待审核 JSONL。

处理流程：

```text
原始材料
  -> 放入 raw/ 或引用外部本地文件
  -> 抽取文本到 processed/
  -> 人工整理成原创表达
  -> 补充 skill_tags、difficulty、reference_answer、scoring_rubric
  -> 使用 schemas/question_bank_item.schema.json 校验
  -> 移动到 seeds/
  -> 导入 PostgreSQL 并生成 embedding
```

注意：不要把大段受版权保护的原文直接放入题库。题库应维护为自己的总结、改写和结构化评分标准。
