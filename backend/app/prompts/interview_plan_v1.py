INTERVIEW_PLAN_V1_VERSION = "interview_plan_v1"

INTERVIEW_PLAN_V1 = """\
请基于岗位 JD、简历、岗位评测和历史报告，制定本场模拟面试计划。

要求：
- 列出必须覆盖的技能（优先从 JD 提取）。
- 安排题型比例：知识题（八股）与简历项目深挖题。
- 设定难度（默认 medium）和最大主问题数。
- 识别简历项目中的风险点（如经验不足、责任不清晰的模块）。

输出 JSON：
{
  "must_cover_skills": ["技能A"],
  "question_type_targets": {"skill": 3, "project_deep_dive": 2, "scenario": 1, "foundation": 1},
  "difficulty": "medium",
  "max_main_questions": 8,
  "project_risk_points": ["简历项目风险点"]
}
"""
