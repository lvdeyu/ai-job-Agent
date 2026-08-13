from __future__ import annotations

import re
from typing import Any

DIMENSION_WEIGHTS = {
    "skill_match": 0.30,
    "experience_match": 0.25,
    "behavioral_culture": 0.15,
    "compensation": 0.10,
    "work_intensity": 0.10,
    "stability_compliance": 0.05,
    "commute_city": 0.05,
}

DIMENSION_NAMES = {
    "skill_match": "技能匹配",
    "experience_match": "经验匹配",
    "behavioral_culture": "行为文化",
    "compensation": "薪资结构",
    "work_intensity": "工作强度",
    "stability_compliance": "稳定性与合规",
    "commute_city": "通勤与城市",
}

SKILL_ALIASES = {
    "Agent": ["agent", "智能体", "工具调用", "tool calling", "function calling"],
    "RAG": ["rag", "检索增强", "知识库", "向量检索"],
    "LangGraph": ["langgraph"],
    "LangChain": ["langchain"],
    "Python": ["python"],
    "FastAPI": ["fastapi"],
    "Java": ["java"],
    "Spring Boot": ["spring boot", "springboot"],
    "React": ["react"],
    "TypeScript": ["typescript", "ts"],
    "Vue": ["vue"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "数据库"],
    "Redis": ["redis"],
    "Docker": ["docker", "容器"],
    "LLM": ["llm", "大模型"],
    "Prompt": ["prompt", "提示词"],
}

GENERAL_DEALBREAKERS = ["996", "纯 on-call", "纯on-call", "外包", "劳务派遣", "无薪"]
INTENSITY_MARKERS = ["996", "大小周", "抗压", "高压", "快节奏", "on-call", "oncall", "加班"]
INTERNSHIP_MARKERS = ["实习", "在校", "应届", "校招", "校园", "元/天", "天/周"]
SENIOR_EXPERIENCE_PATTERNS = [r"\d+\s*-\s*\d+\s*年", r"\d+\s*年以上", r"\d+\s*年及以上"]
LANGUAGE_REQUIREMENTS = ["英语", "英文", "日语", "日文", "韩语", "韩文"]
PREFERRED_REQUIREMENT_MARKERS = [
    "优先",
    "加分",
    "加分项",
    "更佳",
    "最好",
    "preferred",
    "plus",
    "bonus",
]
REQUIRED_REQUIREMENT_MARKERS = [
    "必须",
    "要求",
    "需要",
    "熟悉",
    "掌握",
    "精通",
    "具备",
    "能够",
    "负责",
    "开发",
    "建设",
    "经验",
    "能力",
]
STRONG_REQUIRED_REQUIREMENT_MARKERS = [
    "必须",
    "要求",
    "需要",
    "熟悉",
    "掌握",
    "精通",
    "具备",
    "能够",
]
JD_CONTEXT_SEPARATORS = "。；;，,\n"


def build_job_evaluation_report(
    job: Any,
    resume_version: Any,
    profile: Any | None,
) -> dict[str, Any]:
    job_text = _compact(
        " ".join(
            [
                job.title or "",
                job.company or "",
                job.location or "",
                job.salary or "",
                job.experience or "",
                job.education or "",
                job.tags or "",
                job.description or "",
            ]
        )
    )
    resume_text = _compact(resume_version.extracted_text or "")
    profile_text = _compact(
        " ".join(
            [
                getattr(profile, "target_role", "") or "",
                getattr(profile, "cities", "") or "",
                getattr(profile, "deal_breakers", "") or "",
                getattr(profile, "work_type", "") or "",
            ]
        )
    )

    resume_skills = _detect_skills(resume_text)
    jd_requirements = _build_jd_requirements(job_text, resume_skills)
    matched_skills = _unique(
        jd_requirements["matched_required_skills"]
        + jd_requirements["matched_preferred_skills"]
    )
    missing_skills = _unique(
        jd_requirements["missing_required_skills"]
        + jd_requirements["missing_preferred_skills"]
    )

    dealbreakers_hit = _detect_dealbreakers(job_text, getattr(profile, "deal_breakers", None))
    language_gate_triggered, language_gaps = _detect_language_gate(
        job_text,
        resume_text,
        profile_text,
    )

    dimensions = {
        "skill_match": _score_skill_match(jd_requirements),
        "experience_match": _score_experience_match(job_text, resume_text),
        "behavioral_culture": _score_behavioral_culture(job_text, profile_text, dealbreakers_hit),
        "compensation": _score_compensation(job.salary, profile),
        "work_intensity": _score_work_intensity(job_text),
        "stability_compliance": _score_stability_compliance(job_text),
        "commute_city": _score_commute_city(job.location, profile),
    }
    for key, weight in DIMENSION_WEIGHTS.items():
        dimensions[key]["weight"] = weight
    raw_weighted_score = round(
        sum(dimensions[key]["score"] * DIMENSION_WEIGHTS[key] for key in DIMENSION_WEIGHTS),
        1,
    )
    final_score = (
        min(raw_weighted_score, 30.0)
        if dealbreakers_hit or language_gate_triggered
        else raw_weighted_score
    )
    recommendation = _recommendation(final_score)

    highlights = _build_highlights(jd_requirements, dimensions)
    risks_and_gaps = _build_risks(jd_requirements, dimensions, dealbreakers_hit, language_gaps)
    resume_focus_suggestions = _build_resume_suggestions(jd_requirements, job.title)
    honest_gap_statements = _build_honest_gap_statements(
        jd_requirements,
        dealbreakers_hit,
        language_gaps,
    )
    evidence = _build_evidence(job, jd_requirements)
    salary_benchmark = _salary_benchmark(job.salary, profile)

    one_sentence_reason = _one_sentence_reason(
        final_score,
        recommendation,
        matched_skills,
        missing_skills,
        dealbreakers_hit,
        language_gate_triggered,
    )

    return {
        "framework_version": "v1",
        "prompt_version": "local-rule-v1",
        "raw_weighted_score": raw_weighted_score,
        "final_score": round(final_score, 1),
        "recommendation": recommendation,
        "one_sentence_reason": one_sentence_reason,
        "language_gate_triggered": language_gate_triggered,
        "dealbreakers_hit": dealbreakers_hit,
        "jd_requirements": jd_requirements,
        "dimensions": dimensions,
        "highlights": highlights,
        "risks_and_gaps": risks_and_gaps,
        "salary_benchmark": salary_benchmark,
        "evidence": evidence,
        "resume_focus_suggestions": resume_focus_suggestions,
        "honest_gap_statements": honest_gap_statements,
    }


def _build_jd_requirements(job_text: str, resume_skills: list[str]) -> dict[str, Any]:
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    required_evidence: dict[str, str] = {}
    preferred_evidence: dict[str, str] = {}

    for skill, aliases in SKILL_ALIASES.items():
        contexts = _skill_contexts(job_text, aliases)
        if not contexts:
            continue
        is_preferred = any(_looks_preferred(context) for context in contexts)
        has_strong_required = any(_looks_strong_required(context) for context in contexts)
        is_required = has_strong_required or (
            not is_preferred and any(_looks_required(context) for context in contexts)
        )
        evidence = _best_context(contexts)
        if is_preferred and not is_required:
            preferred_skills.append(skill)
            preferred_evidence[skill] = evidence
        else:
            required_skills.append(skill)
            required_evidence[skill] = evidence

    required_skills = _unique(required_skills)
    preferred_skills = _unique(
        [skill for skill in preferred_skills if skill not in required_skills]
    )
    matched_required = [skill for skill in required_skills if skill in resume_skills]
    missing_required = [skill for skill in required_skills if skill not in resume_skills]
    matched_preferred = [skill for skill in preferred_skills if skill in resume_skills]
    missing_preferred = [skill for skill in preferred_skills if skill not in resume_skills]

    return {
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,
        "matched_preferred_skills": matched_preferred,
        "missing_preferred_skills": missing_preferred,
        "required_evidence": required_evidence,
        "preferred_evidence": preferred_evidence,
    }


def _score_skill_match(jd_requirements: dict[str, Any]) -> dict[str, Any]:
    required_skills = jd_requirements["required_skills"]
    preferred_skills = jd_requirements["preferred_skills"]
    matched_required = jd_requirements["matched_required_skills"]
    missing_required = jd_requirements["missing_required_skills"]
    matched_preferred = jd_requirements["matched_preferred_skills"]
    missing_preferred = jd_requirements["missing_preferred_skills"]
    job_skills = _unique(required_skills + preferred_skills)
    if not job_skills:
        return _dimension(
            50,
            "insufficient_data",
            "JD 未提取到明确技能要求，按信息不足中性分处理。",
        )

    required_ratio = len(matched_required) / len(required_skills) if required_skills else 1
    preferred_ratio = len(matched_preferred) / len(preferred_skills) if preferred_skills else 1
    if required_skills and preferred_skills:
        score = round(30 + 55 * required_ratio + 15 * preferred_ratio)
    elif required_skills:
        score = round(35 + 65 * required_ratio)
    else:
        score = round(55 + 45 * preferred_ratio)

    explanation = (
        f"JD 必备：{_join(required_skills) or '未明确'}；"
        f"必备命中：{_join(matched_required) or '暂无'}；"
        f"必备缺口：{_join(missing_required) or '暂无'}；"
        f"加分项：{_join(preferred_skills) or '未明确'}；"
        f"加分命中：{_join(matched_preferred) or '暂无'}；"
        f"加分缺口：{_join(missing_preferred) or '暂无'}。"
    )
    return _dimension(score, "sufficient", explanation)


def _score_experience_match(job_text: str, resume_text: str) -> dict[str, Any]:
    is_internship = any(marker in job_text for marker in INTERNSHIP_MARKERS)
    is_senior = any(re.search(pattern, job_text) for pattern in SENIOR_EXPERIENCE_PATTERNS)
    has_project = any(
        marker in resume_text.lower()
        for marker in ["项目", "project", "实习", "开发", "backend", "agent"]
    )
    if is_senior and not any(marker in resume_text for marker in ["年", "实习", "工作"]):
        return _dimension(42, "sufficient", "JD 有明确年限要求，但简历未展示对应工作年限。")
    if is_internship and has_project:
        return _dimension(78, "sufficient", "岗位偏实习/校招，简历已有项目或开发经历可支撑。")
    if has_project:
        return _dimension(
            65,
            "sufficient",
            "简历展示了项目或开发经历，但 JD 年限/职责细节仍需进一步对齐。",
        )
    return _dimension(50, "insufficient_data", "简历经历结构不足，暂按中性分处理。")


def _score_behavioral_culture(
    job_text: str,
    profile_text: str,
    dealbreakers_hit: list[str],
) -> dict[str, Any]:
    if dealbreakers_hit:
        return _dimension(25, "sufficient", f"岗位触发不可接受条件：{_join(dealbreakers_hit)}。")
    culture_signals = ["协作", "沟通", "自主", "owner", "质量", "快速", "学习"]
    hits = [signal for signal in culture_signals if signal.lower() in job_text.lower()]
    profile_hits = [signal for signal in culture_signals if signal.lower() in profile_text.lower()]
    if not hits:
        return _dimension(
            50,
            "insufficient_data",
            "JD 缺少明确团队文化或行为要求，按信息不足中性分处理。",
        )
    score = 70 if not profile_hits else min(90, 65 + 5 * len(set(hits) & set(profile_hits)))
    return _dimension(score, "sufficient", f"JD 行为文化信号：{_join(hits)}。")


def _score_compensation(salary: str | None, profile: Any | None) -> dict[str, Any]:
    salary_range = _parse_salary_range(salary)
    expected_min = getattr(profile, "salary_min", None) if profile else None
    expected_max = getattr(profile, "salary_max", None) if profile else None
    if not salary_range or expected_min is None:
        return _dimension(50, "insufficient_data", "薪资或个人期望薪资不足，按中性分处理。")
    low, high, unit = salary_range
    if unit != "day":
        return _dimension(55, "insufficient_data", "JD 薪资不是日薪口径，首版暂不做精确折算。")
    expected_high = expected_max or expected_min
    overlaps = high >= expected_min and low <= expected_high
    if overlaps:
        return _dimension(82, "sufficient", f"JD 日薪 {low}-{high} 元与期望区间有重叠。")
    if high < expected_min:
        return _dimension(
            40,
            "sufficient",
            f"JD 日薪上限 {high} 元低于期望下限 {expected_min} 元。",
        )
    return _dimension(65, "sufficient", "JD 日薪高于期望区间，需确认工作强度和岗位质量。")


def _score_work_intensity(job_text: str) -> dict[str, Any]:
    hits = [marker for marker in INTENSITY_MARKERS if marker.lower() in job_text.lower()]
    if hits:
        score = 25 if any(marker in hits for marker in ["996", "大小周"]) else 45
        return _dimension(score, "sufficient", f"JD 出现工作强度信号：{_join(hits)}。")
    return _dimension(50, "insufficient_data", "JD 未提供工作强度信息，按中性分处理。")


def _score_stability_compliance(job_text: str) -> dict[str, Any]:
    if any(marker in job_text for marker in ["外包", "劳务派遣", "第三方"]):
        return _dimension(25, "sufficient", "JD 出现外包/派遣等稳定性或合规风险信号。")
    if any(marker in job_text for marker in ["五险一金", "上市", "融资"]):
        return _dimension(68, "sufficient", "JD 出现部分稳定性或合规正向信号。")
    return _dimension(50, "insufficient_data", "缺少公司稳定性、合规和福利信息，按中性分处理。")


def _score_commute_city(location: str | None, profile: Any | None) -> dict[str, Any]:
    cities = getattr(profile, "cities", None) if profile else None
    if not location or not cities:
        return _dimension(50, "insufficient_data", "岗位城市或用户意愿城市缺失，按中性分处理。")
    normalized_cities = [city.strip() for city in re.split(r"[,，、\s]+", cities) if city.strip()]
    if any(city in location for city in normalized_cities):
        return _dimension(88, "sufficient", f"岗位城市 {location} 命中意愿城市。")
    return _dimension(
        45,
        "sufficient",
        f"岗位城市 {location} 未命中意愿城市：{_join(normalized_cities)}。",
    )


def _dimension(score: int | float, data_status: str, explanation: str) -> dict[str, Any]:
    return {
        "score": max(0, min(100, round(float(score), 1))),
        "weight": 0,
        "data_status": data_status,
        "explanation": explanation,
    }


def _skill_contexts(text: str, aliases: list[str]) -> list[str]:
    normalized = text.lower()
    contexts = []
    for alias in aliases:
        alias_pattern = _alias_pattern(alias.lower())
        for match in re.finditer(alias_pattern, normalized):
            start, end = _clause_bounds(text, match.start(), match.end())
            contexts.append(_compact(text[start:end]))
    return contexts


def _clause_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = max(text.rfind(separator, 0, start) for separator in JD_CONTEXT_SEPARATORS)
    right_candidates = [
        index for separator in JD_CONTEXT_SEPARATORS if (index := text.find(separator, end)) != -1
    ]
    clause_start = left + 1 if left >= 0 else max(0, start - 42)
    clause_end = min(right_candidates) if right_candidates else min(len(text), end + 42)
    return clause_start, clause_end


def _alias_pattern(alias: str) -> str:
    if re.fullmatch(r"[a-z0-9+#.\s-]+", alias):
        return rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
    return re.escape(alias)


def _looks_preferred(context: str) -> bool:
    lowered = context.lower()
    return any(marker.lower() in lowered for marker in PREFERRED_REQUIREMENT_MARKERS)


def _looks_required(context: str) -> bool:
    lowered = context.lower()
    return any(marker.lower() in lowered for marker in REQUIRED_REQUIREMENT_MARKERS)


def _looks_strong_required(context: str) -> bool:
    lowered = context.lower()
    return any(marker.lower() in lowered for marker in STRONG_REQUIRED_REQUIREMENT_MARKERS)


def _best_context(contexts: list[str]) -> str:
    if not contexts:
        return ""
    preferred = sorted(contexts, key=len)
    return preferred[0][:160]


def _detect_skills(text: str) -> list[str]:
    normalized = text.lower()
    detected = []
    for skill, aliases in SKILL_ALIASES.items():
        if any(_contains_alias(normalized, alias.lower()) for alias in aliases):
            detected.append(skill)
    return detected


def _contains_alias(text: str, alias: str) -> bool:
    return re.search(_alias_pattern(alias), text) is not None


def _detect_dealbreakers(job_text: str, profile_dealbreakers: str | None) -> list[str]:
    candidates = list(GENERAL_DEALBREAKERS)
    if profile_dealbreakers:
        for raw in re.split(r"[,，、\n;；]+", profile_dealbreakers):
            cleaned = raw.strip()
            cleaned = re.sub(r"^(不接受|不能接受|拒绝|不要)", "", cleaned).strip()
            if cleaned:
                candidates.append(cleaned)
    hits = []
    lowered = job_text.lower()
    for candidate in candidates:
        if candidate and candidate.lower() in lowered:
            hits.append(candidate)
    return list(dict.fromkeys(hits))


def _detect_language_gate(
    job_text: str,
    resume_text: str,
    profile_text: str,
) -> tuple[bool, list[str]]:
    gaps = []
    combined_profile = f"{resume_text} {profile_text}"
    for language in LANGUAGE_REQUIREMENTS:
        if language in job_text and language not in combined_profile:
            gaps.append(language)
    return bool(gaps), gaps


def _parse_salary_range(salary: str | None) -> tuple[int, int, str] | None:
    if not salary:
        return None
    day_match = re.search(r"(\d+)\s*-\s*(\d+)\s*元\s*/?\s*天", salary)
    if day_match:
        return int(day_match.group(1)), int(day_match.group(2)), "day"
    k_match = re.search(r"(\d+)\s*-\s*(\d+)\s*[kK]", salary)
    if k_match:
        return int(k_match.group(1)), int(k_match.group(2)), "month_k"
    return None


def _salary_benchmark(salary: str | None, profile: Any | None) -> dict[str, Any]:
    expected_min = getattr(profile, "salary_min", None) if profile else None
    expected_max = getattr(profile, "salary_max", None) if profile else None
    if salary:
        return {
            "value": salary,
            "is_estimate": False,
            "evidence": "直接来自岗位薪资字段。",
        }
    if expected_min is not None:
        value = f"用户期望 {expected_min}-{expected_max or expected_min} 元/天"
        return {
            "value": value,
            "is_estimate": True,
            "evidence": "岗位未提供薪资，仅引用用户期望。",
        }
    return {
        "value": "暂无可靠薪资信息",
        "is_estimate": True,
        "evidence": "JD 与用户配置均缺少薪资口径。",
    }


def _recommendation(score: float) -> str:
    if score >= 85:
        return "强烈投递"
    if score >= 70:
        return "可投递"
    if score >= 50:
        return "观望"
    return "不建议"


def _one_sentence_reason(
    score: float,
    recommendation: str,
    matched_skills: list[str],
    missing_skills: list[str],
    dealbreakers_hit: list[str],
    language_gate_triggered: bool,
) -> str:
    if dealbreakers_hit or language_gate_triggered:
        return "岗位触发硬性风险或语言闸门，按评估框架将总分封顶，建议谨慎处理。"
    if matched_skills:
        return (
            f"当前建议为{recommendation}，核心依据是已命中 "
            f"{_join(matched_skills)}，总分 {score}/100。"
        )
    if missing_skills:
        return (
            f"当前建议为{recommendation}，主要风险是缺少 "
            f"{_join(missing_skills)} 等岗位关键要求。"
        )
    return f"当前建议为{recommendation}，但 JD 或简历信息不足，建议补充材料后复评。"


def _build_highlights(
    jd_requirements: dict[str, Any],
    dimensions: dict[str, dict[str, Any]],
) -> list[str]:
    highlights = []
    matched_required = jd_requirements["matched_required_skills"]
    matched_preferred = jd_requirements["matched_preferred_skills"]
    if matched_required:
        highlights.append(f"简历已覆盖 JD 必备技能：{_join(matched_required)}。")
    if matched_preferred:
        highlights.append(f"简历也覆盖 JD 加分项：{_join(matched_preferred)}。")
    strong_dimensions = [
        DIMENSION_NAMES[key] for key, value in dimensions.items() if value["score"] >= 75
    ]
    if strong_dimensions:
        highlights.append(f"强项维度：{_join(strong_dimensions)}。")
    return highlights[:3] or ["暂未发现明显强匹配点，建议先完善简历项目和技能表达。"]


def _build_risks(
    jd_requirements: dict[str, Any],
    dimensions: dict[str, dict[str, Any]],
    dealbreakers_hit: list[str],
    language_gaps: list[str],
) -> list[str]:
    risks = []
    missing_required = jd_requirements["missing_required_skills"]
    missing_preferred = jd_requirements["missing_preferred_skills"]
    if missing_required:
        risks.append(f"JD 必备技能缺口：{_join(missing_required)}。")
    if missing_preferred:
        risks.append(f"JD 加分项未体现：{_join(missing_preferred)}。")
    if dealbreakers_hit:
        risks.append(f"命中不可接受条件：{_join(dealbreakers_hit)}。")
    if language_gaps:
        risks.append(f"语言闸门缺口：JD 要求 {_join(language_gaps)}，简历/画像未声明。")
    insufficient = [
        DIMENSION_NAMES[key]
        for key, value in dimensions.items()
        if value["data_status"] == "insufficient_data"
    ]
    if insufficient:
        risks.append(f"信息不足维度：{_join(insufficient)}，已按中性分处理。")
    return risks[:4]


def _build_resume_suggestions(
    jd_requirements: dict[str, Any],
    job_title: str,
) -> list[str]:
    suggestions = []
    matched_required = jd_requirements["matched_required_skills"]
    missing_required = jd_requirements["missing_required_skills"]
    matched_preferred = jd_requirements["matched_preferred_skills"]
    missing_preferred = jd_requirements["missing_preferred_skills"]
    if matched_required:
        suggestions.append(
            f"把 JD 必备技能 {_join(matched_required)} 对应项目放到简历前半部分，"
            "补充场景、动作和结果。"
        )
    if missing_required:
        suggestions.append(
            f"JD 必备缺口是 {_join(missing_required[:3])}；"
            "如果真实掌握，补项目证据，不会的不要硬写。"
        )
    if matched_preferred:
        suggestions.append(
            f"把加分项 {_join(matched_preferred)} 放进技术栈或项目亮点，作为差异化优势。"
        )
    if missing_preferred and not missing_required:
        suggestions.append(
            f"加分项 {_join(missing_preferred[:3])} 暂未体现，可作为后续学习或面试补充点。"
        )
    suggestions.append(f"围绕“{job_title}”补一段 2-3 行岗位匹配摘要，强调可实习交付能力。")
    return suggestions[:3]


def _build_honest_gap_statements(
    jd_requirements: dict[str, Any],
    dealbreakers_hit: list[str],
    language_gaps: list[str],
) -> list[str]:
    statements = []
    missing_required = jd_requirements["missing_required_skills"]
    missing_preferred = jd_requirements["missing_preferred_skills"]
    if missing_required:
        statements.append(
            f"对 JD 必备缺口 {_join(missing_required[:3])} 的掌握程度需要如实描述，"
            "不要伪造成熟经验。"
        )
    if missing_preferred:
        statements.append(
            f"加分项 {_join(missing_preferred[:3])} 可以不强行写入，避免简历过度包装。"
        )
    if dealbreakers_hit:
        statements.append("如果仍想沟通该岗位，应先向 HR 确认触发风险是否真实存在。")
    if language_gaps:
        statements.append(f"如岗位强制要求 {_join(language_gaps)}，需要先补充真实语言能力证明。")
    return statements


def _build_evidence(job: Any, jd_requirements: dict[str, Any]) -> list[str]:
    evidence = [
        f"岗位：{job.company} · {job.title}",
    ]
    if job.salary:
        evidence.append(f"薪资字段：{job.salary}")
    if job.location:
        evidence.append(f"城市字段：{job.location}")
    required_skills = jd_requirements["required_skills"]
    preferred_skills = jd_requirements["preferred_skills"]
    matched_required = jd_requirements["matched_required_skills"]
    missing_required = jd_requirements["missing_required_skills"]
    matched_preferred = jd_requirements["matched_preferred_skills"]
    missing_preferred = jd_requirements["missing_preferred_skills"]
    if required_skills:
        evidence.append(f"JD 必备技能：{_join(required_skills)}")
    if preferred_skills:
        evidence.append(f"JD 加分项：{_join(preferred_skills)}")
    if matched_required or matched_preferred:
        matched = _unique(matched_required + matched_preferred)
        evidence.append(f"简历命中：{_join(matched)}")
    if missing_required or missing_preferred:
        missing = _unique(missing_required + missing_preferred)
        evidence.append(f"简历缺口：{_join(missing)}")
    return evidence


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _join(values: list[str]) -> str:
    return "、".join(values)
