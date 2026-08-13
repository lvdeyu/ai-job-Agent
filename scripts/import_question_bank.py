#!/usr/bin/env python3
"""Validate and optionally import interview question-bank seed files.

Default mode is safe: it only validates JSONL seed files and prints a summary.
Use --write-db to upsert rows into PostgreSQL, and --with-embeddings to call an
OpenAI-compatible embeddings endpoint before import.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BANK_DIR = PROJECT_ROOT / "knowledge" / "interview_question_bank"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

QUESTION_TYPES = {
    "skill",
    "project_deep_dive",
    "scenario",
    "foundation",
    "followup",
    "behavioral",
}
DIFFICULTIES = {"easy", "medium", "hard"}
SOURCE_TYPES = {
    "original",
    "course_note",
    "book_note",
    "interview_experience",
    "web_summary",
}
REQUIRED_FIELDS = {
    "id",
    "locale",
    "domain",
    "question_type",
    "difficulty",
    "skill_tags",
    "question_text",
    "reference_answer",
    "scoring_rubric",
    "followup_suggestions",
    "embedding_text",
    "source",
    "version",
}


@dataclass
class QuestionItem:
    path: Path
    line_no: int
    data: dict[str, Any]
    content_hash: str


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def stable_hash(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def expect_type(
    errors: list[str],
    value: Any,
    expected_type: type | tuple[type, ...],
    field_name: str,
) -> bool:
    if isinstance(value, expected_type):
        return True
    errors.append(f"{field_name} 类型错误")
    return False


def validate_item(data: dict[str, Any], location: str) -> list[str]:
    errors: list[str] = []

    missing = sorted(REQUIRED_FIELDS - set(data))
    extra = sorted(set(data) - REQUIRED_FIELDS)
    if missing:
        errors.append(f"缺少字段: {', '.join(missing)}")
    if extra:
        errors.append(f"存在未声明字段: {', '.join(extra)}")

    if not missing:
        if not expect_type(errors, data["id"], str, "id") or len(data["id"]) < 6:
            errors.append("id 至少 6 个字符")
        if data.get("locale") != "zh-CN":
            errors.append("locale 当前只允许 zh-CN")
        if not expect_type(errors, data.get("domain"), str, "domain"):
            pass
        if data.get("question_type") not in QUESTION_TYPES:
            errors.append(f"question_type 不合法: {data.get('question_type')}")
        if data.get("difficulty") not in DIFFICULTIES:
            errors.append(f"difficulty 不合法: {data.get('difficulty')}")

        skill_tags = data.get("skill_tags")
        if expect_type(errors, skill_tags, list, "skill_tags"):
            if not skill_tags:
                errors.append("skill_tags 不能为空")
            if len(skill_tags) != len(set(skill_tags)):
                errors.append("skill_tags 不能重复")
            if not all(isinstance(tag, str) and tag.strip() for tag in skill_tags):
                errors.append("skill_tags 每一项都必须是非空字符串")

        for field_name in ("question_text", "reference_answer", "embedding_text"):
            if expect_type(errors, data.get(field_name), str, field_name):
                if len(data[field_name].strip()) < 10:
                    errors.append(f"{field_name} 内容过短")

        rubric = data.get("scoring_rubric")
        if expect_type(errors, rubric, list, "scoring_rubric"):
            if not rubric:
                errors.append("scoring_rubric 不能为空")
            total_points = 0
            for index, criterion in enumerate(rubric, start=1):
                prefix = f"scoring_rubric[{index}]"
                if not isinstance(criterion, dict):
                    errors.append(f"{prefix} 必须是对象")
                    continue
                for field_name in ("criterion", "excellent_signal", "weak_signal"):
                    if not isinstance(criterion.get(field_name), str) or not criterion[field_name].strip():
                        errors.append(f"{prefix}.{field_name} 必须是非空字符串")
                points = criterion.get("points")
                if not isinstance(points, int) or not 1 <= points <= 100:
                    errors.append(f"{prefix}.points 必须是 1-100 的整数")
                else:
                    total_points += points
            if total_points != 100:
                errors.append(f"scoring_rubric 分值总和应为 100，当前为 {total_points}")

        followups = data.get("followup_suggestions")
        if expect_type(errors, followups, list, "followup_suggestions"):
            if not all(isinstance(item, str) for item in followups):
                errors.append("followup_suggestions 每一项都必须是字符串")

        source = data.get("source")
        if expect_type(errors, source, dict, "source"):
            if source.get("type") not in SOURCE_TYPES:
                errors.append(f"source.type 不合法: {source.get('type')}")
            if not isinstance(source.get("name"), str) or not source["name"].strip():
                errors.append("source.name 必须是非空字符串")

        if not isinstance(data.get("version"), int) or data["version"] < 1:
            errors.append("version 必须是大于等于 1 的整数")

    return [f"{location}: {error}" for error in errors]


def load_question_items(bank_dir: Path, pattern: str) -> tuple[list[QuestionItem], list[str]]:
    seed_dir = bank_dir / "seeds"
    if not seed_dir.exists():
        return [], [f"题库目录不存在: {seed_dir}"]

    items: list[QuestionItem] = []
    errors: list[str] = []
    seen_ids: dict[str, str] = {}

    for path in sorted(seed_dir.glob(pattern)):
        for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            location = f"{path.relative_to(PROJECT_ROOT)}:{line_no}"
            try:
                data = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                errors.append(f"{location}: JSON 解析失败: {exc.msg}")
                continue
            if not isinstance(data, dict):
                errors.append(f"{location}: 每行必须是 JSON 对象")
                continue

            errors.extend(validate_item(data, location))
            item_id = data.get("id")
            if isinstance(item_id, str):
                previous = seen_ids.get(item_id)
                if previous:
                    errors.append(f"{location}: id 与 {previous} 重复: {item_id}")
                seen_ids[item_id] = location

            items.append(QuestionItem(path=path, line_no=line_no, data=data, content_hash=stable_hash(data)))

    if not items and not errors:
        errors.append(f"没有找到题库文件: {seed_dir / pattern}")

    return items, errors


def batch(items: list[QuestionItem], size: int) -> list[list[QuestionItem]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def fetch_embeddings(items: list[QuestionItem], batch_size: int) -> dict[str, list[float]]:
    api_key = os.environ.get("EMBEDDING_API_KEY")
    base_url = os.environ.get("EMBEDDING_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    timeout = float(os.environ.get("EMBEDDING_TIMEOUT_SECONDS", "60"))

    if not api_key:
        raise RuntimeError("缺少 EMBEDDING_API_KEY，无法生成 embedding")

    embeddings: dict[str, list[float]] = {}
    endpoint = f"{base_url}/embeddings"

    for group in batch(items, batch_size):
        payload = {
            "model": model,
            "input": [item.data["embedding_text"] for item in group],
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"embedding 接口返回 HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"embedding 接口请求失败: {exc.reason}") from exc

        vectors = body.get("data")
        if not isinstance(vectors, list) or len(vectors) != len(group):
            raise RuntimeError("embedding 接口返回结构不符合预期")

        for item, vector_data in zip(group, vectors, strict=True):
            vector = vector_data.get("embedding") if isinstance(vector_data, dict) else None
            if not isinstance(vector, list) or not all(isinstance(value, (int, float)) for value in vector):
                raise RuntimeError(f"embedding 结果非法: {item.data['id']}")
            embeddings[item.data["id"]] = [float(value) for value in vector]

    return embeddings


def vector_literal(vector: list[float] | None) -> str | None:
    if vector is None:
        return None
    return "[" + ",".join(f"{value:.8g}" for value in vector) + "]"


def import_to_postgres(items: list[QuestionItem], embeddings: dict[str, list[float]] | None) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("缺少 DATABASE_URL，无法写入 PostgreSQL")

    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("缺少 psycopg 依赖，请先安装: pip install 'psycopg[binary]'") from exc

    create_sql = """
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS question_bank_items (
      external_id TEXT PRIMARY KEY,
      locale TEXT NOT NULL,
      domain TEXT NOT NULL,
      question_type TEXT NOT NULL,
      difficulty TEXT NOT NULL,
      skill_tags JSONB NOT NULL,
      question_text TEXT NOT NULL,
      reference_answer TEXT NOT NULL,
      scoring_rubric JSONB NOT NULL,
      followup_suggestions JSONB NOT NULL,
      embedding_text TEXT NOT NULL,
      source JSONB NOT NULL,
      version INTEGER NOT NULL,
      content_hash TEXT NOT NULL,
      embedding vector,
      embedding_model TEXT,
      source_file TEXT NOT NULL,
      source_line INTEGER NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_question_bank_domain ON question_bank_items (domain);
    CREATE INDEX IF NOT EXISTS idx_question_bank_type ON question_bank_items (question_type);
    CREATE INDEX IF NOT EXISTS idx_question_bank_skill_tags
      ON question_bank_items USING GIN (skill_tags);
    """

    upsert_sql = """
    INSERT INTO question_bank_items (
      external_id,
      locale,
      domain,
      question_type,
      difficulty,
      skill_tags,
      question_text,
      reference_answer,
      scoring_rubric,
      followup_suggestions,
      embedding_text,
      source,
      version,
      content_hash,
      embedding,
      embedding_model,
      source_file,
      source_line
    )
    VALUES (
      %(external_id)s,
      %(locale)s,
      %(domain)s,
      %(question_type)s,
      %(difficulty)s,
      %(skill_tags)s::jsonb,
      %(question_text)s,
      %(reference_answer)s,
      %(scoring_rubric)s::jsonb,
      %(followup_suggestions)s::jsonb,
      %(embedding_text)s,
      %(source)s::jsonb,
      %(version)s,
      %(content_hash)s,
      %(embedding)s::vector,
      %(embedding_model)s,
      %(source_file)s,
      %(source_line)s
    )
    ON CONFLICT (external_id) DO UPDATE SET
      locale = EXCLUDED.locale,
      domain = EXCLUDED.domain,
      question_type = EXCLUDED.question_type,
      difficulty = EXCLUDED.difficulty,
      skill_tags = EXCLUDED.skill_tags,
      question_text = EXCLUDED.question_text,
      reference_answer = EXCLUDED.reference_answer,
      scoring_rubric = EXCLUDED.scoring_rubric,
      followup_suggestions = EXCLUDED.followup_suggestions,
      embedding_text = EXCLUDED.embedding_text,
      source = EXCLUDED.source,
      version = EXCLUDED.version,
      content_hash = EXCLUDED.content_hash,
      embedding = EXCLUDED.embedding,
      embedding_model = EXCLUDED.embedding_model,
      source_file = EXCLUDED.source_file,
      source_line = EXCLUDED.source_line,
      updated_at = now();
    """

    embedding_model = os.environ.get("EMBEDDING_MODEL") if embeddings else None
    rows = []
    for item in items:
        data = item.data
        item_id = data["id"]
        rows.append(
            {
                "external_id": item_id,
                "locale": data["locale"],
                "domain": data["domain"],
                "question_type": data["question_type"],
                "difficulty": data["difficulty"],
                "skill_tags": json.dumps(data["skill_tags"], ensure_ascii=False),
                "question_text": data["question_text"],
                "reference_answer": data["reference_answer"],
                "scoring_rubric": json.dumps(data["scoring_rubric"], ensure_ascii=False),
                "followup_suggestions": json.dumps(data["followup_suggestions"], ensure_ascii=False),
                "embedding_text": data["embedding_text"],
                "source": json.dumps(data["source"], ensure_ascii=False),
                "version": data["version"],
                "content_hash": item.content_hash,
                "embedding": vector_literal((embeddings or {}).get(item_id)),
                "embedding_model": embedding_model,
                "source_file": str(item.path.relative_to(PROJECT_ROOT)),
                "source_line": item.line_no,
            }
        )

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(create_sql)
            cursor.executemany(upsert_sql, rows)
        connection.commit()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and import interview question-bank JSONL files.")
    parser.add_argument("--bank-dir", type=Path, default=DEFAULT_BANK_DIR, help="Question-bank root directory.")
    parser.add_argument("--pattern", default="*.jsonl", help="Seed file glob pattern under seeds/.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help="Optional .env file.")
    parser.add_argument("--write-db", action="store_true", help="Upsert validated items into PostgreSQL.")
    parser.add_argument("--with-embeddings", action="store_true", help="Generate embeddings before database import.")
    parser.add_argument("--embedding-batch-size", type=int, default=16, help="Embedding request batch size.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    load_dotenv(args.env_file)

    items, errors = load_question_items(args.bank_dir, args.pattern)
    if errors:
        print("题库校验失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"题库校验通过：{len(items)} 道题")
    domains = sorted({item.data["domain"] for item in items})
    question_types = sorted({item.data["question_type"] for item in items})
    print(f"覆盖方向：{', '.join(domains)}")
    print(f"题型：{', '.join(question_types)}")

    if not args.write_db:
        print("当前为 dry-run：未写入数据库，未调用 embedding 接口")
        return 0

    embeddings: dict[str, list[float]] | None = None
    if args.with_embeddings:
        embeddings = fetch_embeddings(items, args.embedding_batch_size)
        dimension = len(next(iter(embeddings.values()))) if embeddings else 0
        print(f"embedding 生成完成：{len(embeddings)} 条，维度 {dimension}")
    else:
        print("未传 --with-embeddings：将写入题库元数据，embedding 字段为空")

    import_to_postgres(items, embeddings)
    print(f"题库导入完成：{len(items)} 道题")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

