# -*- coding: utf-8 -*-
"""解析《Agent 开发面试深水区·全解析》为结构化候选题库（中间稿）。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "杂乱资料" / "《Agent 开发面试深水区·全解析》.md"
OUT = ROOT / "knowledge" / "interview_question_bank" / "imports" / "processed"

DOMAIN_BY_PART = {
    "第一篇": "agent",
    "第二篇": "rag",
    "第三篇": "llm_tool_use",
    "第四篇": "llm_engineering",
    "第五篇": "langchain",
}

def parse() -> list[dict]:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines()
    questions: list[dict] = []
    current_part = ""
    current_q: dict | None = None
    section = ""

    def flush() -> None:
        nonlocal current_q
        if current_q and current_q.get("question_text"):
            questions.append(current_q)
        current_q = None

    for raw in lines:
        line = raw.rstrip()
        m_part = re.match(r"^#\s*(第[一二三四五]篇)\s+(.*)", line)
        if m_part:
            flush()
            current_part = m_part.group(1)
            continue
        m_q = re.match(r"^##\s+(\d+)\.\s+(.*)", line)
        if m_q:
            flush()
            current_q = {
                "part": current_part,
                "domain": DOMAIN_BY_PART.get(current_part, ""),
                "num": int(m_q.group(1)),
                "question_text": m_q.group(2).strip(),
                "core_answer": [],
                "followups": [],
                "pitfalls": [],
            }
            section = ""
            continue
        if current_q is None:
            continue
        if line.startswith("**核心回答**"):
            section = "core"
            continue
        if line.startswith("**追问预判**"):
            section = "followup"
            continue
        if line.startswith("**坑点警示**"):
            section = "pitfall"
            continue
        if line.strip() == "---":
            continue
        if section == "core" and line.strip():
            current_q["core_answer"].append(line.strip())
        elif section == "followup" and line.strip():
            current_q["followups"].append(line.strip())
        elif section == "pitfall" and line.strip():
            current_q["pitfalls"].append(line.strip())
    flush()
    return questions

def main() -> None:
    questions = parse()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "agent_deep_water.candidates.json"
    payload = {
        "source": str(SRC.relative_to(ROOT)),
        "count": len(questions),
        "questions": questions,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"解析完成: {len(questions)} 题 -> {target.relative_to(ROOT)}")
    by_domain: dict[str, int] = {}
    for q in questions:
        by_domain[q["domain"]] = by_domain.get(q["domain"], 0) + 1
    print("按 domain 分布:", json.dumps(by_domain, ensure_ascii=False))

if __name__ == "__main__":
    sys.exit(main())
