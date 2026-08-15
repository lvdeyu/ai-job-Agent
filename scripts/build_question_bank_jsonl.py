# -*- coding: utf-8 -*-
"""将深水区候选稿转为按 domain 拆分的 JSONL 种子（中间稿，待抽查）。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / "knowledge" / "interview_question_bank" / "imports" / "processed" / "agent_deep_water.candidates.json"
OUT_DIR = ROOT / "knowledge" / "interview_question_bank" / "imports" / "processed"

DOMAIN_TAGS = {
    "agent": ["Agent", "Workflow", "ReAct", "Planning", "Memory", "Reflection", "LLM"],
    "rag": ["RAG", "Embedding", "Vector Database", "Chunking", "Query Rewrite", "Hybrid Search", "Rerank", "Hallucination"],
    "llm_tool_use": ["Function Calling", "MCP", "Tool Use", "SSE", "WebSocket", "A2A", "Skill", "LLM Gateway"],
    "llm_engineering": ["Transformer", "Attention", "Tokenizer", "Fine-tuning", "LoRA", "RLHF", "DPO", "KV Cache", "Quantization", "Prompt Engineering", "CoT", "MoE", "LLM Deployment"],
    "langchain": ["LangChain", "LangGraph", "Chain", "Agent Framework", "Memory", "Deep Research"],
}

RUBRIC_BASE = [
    ("技术正确性", 40, "概念理解准确，能讲清原理、流程和关键细节，术语使用正确。", "概念混淆或流程遗漏关键环节，只停留在表面描述。"),
    ("项目贴合度", 25, "能结合具体项目/场景说明选型与落地，给出实例或取舍依据。", "只背定义，没有结合项目经验或实际场景。"),
    ("表达清晰度", 20, "回答结构清晰，先总后分，逻辑连贯，重点突出。", "回答散乱、无层次，难以抓住要点。"),
    ("风险意识与边界感", 15, "能主动说明局限、风险、边界条件和替代方案。", "忽略风险与边界，把方案说得绝对化。"),
]

def clean_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^[-*]\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def table_to_text(lines: list[str]) -> str:
    """把 markdown 表格（含 --- 分隔行的连续 | 行）转成自然语言描述。"""
    rows: list[list[str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|?$", lines[i + 1].strip()):
            header = [c.strip() for c in line.strip("|").split("|")]
            i += 2  # 跳过表头下一行的分隔行
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if len(cells) >= len(header):
                    rows.append(cells)
                i += 1
            break
        i += 1
    if not rows:
        return ""
    # 用表头列名组织自然语言：第一列是维度名，其余列是方案名
    parts: list[str] = []
    for row in rows:
        dimension = row[0]
        comparisons = []
        for idx in range(1, min(len(row), len(header))):
            option_name = header[idx]
            option_value = row[idx]
            comparisons.append(f"{option_name}是「{option_value}」")
        parts.append(f"{dimension}：{'，'.join(comparisons)}")
    return "；".join(parts) + "。"

def infer_question_type(question: str, core: str) -> str:
    text = question + " " + core
    if re.search(r"(你做过|你使用|你用了|怎么实现|具体怎么做|如何设计|如何落地|如何规避|实际项目)", text):
        return "scenario"
    if re.search(r"(什么是|解释|讲讲|简述|请谈|核心概念|原理是什么|是什么)", text):
        return "foundation"
    if re.search(r"(项目|工程|实现|代码|方案|架构)", text):
        return "project_deep_dive"
    return "skill"

def infer_difficulty(question: str, core: str) -> str:
    text = question + " " + core
    if re.search(r"(深水|复杂|进阶|优化|对比|选型|难点|怎么评估|怎么量化|原理)", text):
        return "hard"
    return "medium"

def pick_tags(question: str, core: str, domain: str) -> list[str]:
    text = question + " " + core
    tags: list[str] = []

    def add(tag: str) -> None:
        if tag and not any(existing.casefold() == tag.casefold() for existing in tags):
            tags.append(tag)

    for tag in DOMAIN_TAGS[domain]:
        if tag.casefold() in text.casefold():
            add(tag)
    if domain == "agent":
        if "记忆" in text:
            add("Memory")
        if re.search(r"多\s*[A-Za-z]*Agent|multi\s*-?\s*agent|多智能体", question, re.I):
            add("Multi-Agent")
    if not tags:
        add(domain.replace("_", " ").title())
    return tags[:8]

def build_rubric(question: str, core: str) -> list[dict]:
    rubric = []
    for criterion, points, exc_tpl, weak_tpl in RUBRIC_BASE:
        rubric.append({
            "criterion": criterion,
            "points": points,
            "excellent_signal": exc_tpl,
            "weak_signal": weak_tpl,
        })
    return rubric

def core_to_answer(core_answer: list[str]) -> str:
    """把核心回答行转成一段自然语言：表格转文字，其余去 markdown。"""
    joined = "\n".join(core_answer)
    if "|" in joined:
        lines = [line.strip() for line in joined.splitlines() if line.strip()]
        table_text = table_to_text(lines)
        # 去掉表格行，保留其余行
        rest_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|?$", lines[i + 1]):
                i += 2
                while i < len(lines) and lines[i].startswith("|"):
                    i += 1
                continue
            rest_lines.append(line)
            i += 1
        rest_text = clean_md(" ".join(rest_lines))
        if table_text:
            return (table_text + " " + rest_text).strip()
        return rest_text
    return clean_md(" ".join(core_answer))

def main() -> None:
    payload = json.loads(CAND.read_text(encoding="utf-8"))
    questions = payload["questions"]
    by_domain: dict[str, list[dict]] = {}
    for q in questions:
        domain = q["domain"]
        num = q["num"]
        question_text = q["question_text"].strip()
        core_clean = core_to_answer(q["core_answer"])
        if len(core_clean) < 10:
            core_clean = " ".join(q["core_answer"]).strip() or question_text
        followups = []
        for line in q["followups"]:
            m = re.match(r"^\d+\.\s*Q[：:]\s*(.*)", line)
            if m:
                followups.append(m.group(1).strip())
        embedding_parts = [question_text] + pick_tags(question_text, core_clean, domain) + [core_clean[:200]]
        item = {
            "id": f"{domain}_deep_{num:03d}",
            "locale": "zh-CN",
            "domain": domain,
            "question_type": infer_question_type(question_text, core_clean),
            "difficulty": infer_difficulty(question_text, core_clean),
            "skill_tags": pick_tags(question_text, core_clean, domain),
            "question_text": question_text,
            "reference_answer": core_clean,
            "scoring_rubric": build_rubric(question_text, core_clean),
            "followup_suggestions": followups,
            "embedding_text": " ".join(embedding_parts)[:1500],
            "source": {"type": "web_summary", "name": "《Agent 开发面试深水区·全解析》"},
            "version": 1,
        }
        by_domain.setdefault(domain, []).append(item)

    for domain, items in by_domain.items():
        target = OUT_DIR / f"{domain}.zh-CN.candidates.jsonl"
        with target.open("w", encoding="utf-8") as fh:
            for item in items:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"{domain}: {len(items)} 题 -> {target.relative_to(ROOT)}")

if __name__ == "__main__":
    sys.exit(main())
