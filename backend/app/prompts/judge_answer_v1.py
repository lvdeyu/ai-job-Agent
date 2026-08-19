JUDGE_ANSWER_V1_VERSION = "judge_answer_v1"

JUDGE_ANSWER_V1 = """\
请对求职者的回答做语义评分解释。最终分数由系统的确定性评分工具计算，你只负责解释和补充证据命中。

要求：
- 对照参考答案和评分 Rubric，指出回答覆盖了哪些要点、缺少哪些要点。
- 区分“回答中明确说出的内容”（事实）与“你的推测”（推测）。
- 不编造用户没有说过的内容。
- 给出简短反馈（2-3 句），语气像面试官点评。

输出 JSON：
{
  "score_explanation": "评分解释",
  "fact_hits": ["命中要点"],
  "inference_notes": ["推测性评价"],
  "feedback": "面向用户的简短反馈"
}
"""
