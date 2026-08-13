# 面试题库目录说明

本目录是模拟面试 RAG 的人工维护知识源。运行时系统会把这里的题目导入 PostgreSQL，并为可检索字段生成 embedding，最终通过 `pgvector` 给 `InterviewAgentGraph` 使用。

## 目录结构

```text
knowledge/interview_question_bank/
  README.md
  schemas/
    question_bank_item.schema.json
  seeds/
    agent_development_intern.zh-CN.jsonl
  rubrics/
    interview_answer_rubric_cn.md
  imports/
    README.md
    raw/
      README.md
    processed/
      README.md
```

## 文件职责

- `schemas/`：题库条目的结构约束，导入前必须校验。
- `seeds/`：项目内置种子题库，按岗位方向或技能域拆分。
- `rubrics/`：通用评分标准，和题目自己的 `scoring_rubric` 一起用于回答评分。
- `imports/raw/`：原始资料区，允许放 `.docx`、`.pdf`、`.md`、`.txt` 或复制文本。
- `imports/processed/`：处理中间稿区，用于保存抽取文本、候选题和待审核 JSONL。

## 题库拆分规则

题库不要全部堆到一个巨大文件里。按“岗位方向 + 语言区域”拆分，文件名使用：

```text
{domain}.{locale}.jsonl
```

示例：

- `agent_development_intern.zh-CN.jsonl`
- `backend_intern.zh-CN.jsonl`
- `rag_vector_database.zh-CN.jsonl`
- `project_deep_dive.zh-CN.jsonl`
- `behavioral.zh-CN.jsonl`

## JSONL 维护规则

- 每行是一个完整 JSON 对象。
- 每道题必须有稳定 `id`，后续不要随意改名。
- `skill_tags` 用于精确过滤，`embedding_text` 用于语义检索。
- `reference_answer` 和 `scoring_rubric` 是评分依据，不直接展示给用户。
- 如果题目来自网络、书籍或课程，必须记录 `source`，不要大段复制受版权保护内容。
- 题目修改后应更新 `version`，保证历史面试报告可以追踪。

## 运行时流向

```text
JSONL 种子题库
  -> Schema 校验
  -> 导入 PostgreSQL question_bank_items
  -> 生成 embedding
  -> pgvector Top-K 检索
  -> InterviewAgentGraph 选题、追问、评分
```

## 原始文档转正式题库

```text
imports/raw/ 或外部本地文档
  -> 抽取文本到 imports/processed/
  -> AI 拆分候选题
  -> AI 补充 reference_answer、scoring_rubric、skill_tags、embedding_text
  -> 人工抽查和改写
  -> seeds/*.jsonl
  -> 导入数据库
```

你后续可以直接提供 Word、PDF、Markdown 或粘贴文本。原始资料不需要手写标准字段；字段由清洗流程生成。

## 校验和导入命令

只校验题库，不写数据库：

```bash
python scripts/import_question_bank.py
```

写入 PostgreSQL，但暂不生成 embedding：

```bash
python scripts/import_question_bank.py --write-db
```

写入 PostgreSQL 并调用 OpenAI-compatible embedding 接口：

```bash
python scripts/import_question_bank.py --write-db --with-embeddings
```

需要的环境变量见项目根目录 `.env.example`。
