from __future__ import annotations

from typing import Any

from app.services.llm import LLMClient, LLMError, ToolSpec


class FakeLLMClient:
    """Scripted LLM client used to test the agent loop without network calls."""

    def __init__(
        self,
        *,
        decisions: list[dict[str, Any]] | None = None,
        opening: str = "你好，我是今天的面试官，请先做一个自我介绍。",
        tool_calls: list[Any] | None = None,
        fail_tools: bool = False,
        fail_json: bool = False,
    ) -> None:
        self.decisions = decisions or []
        self.opening = opening
        self.tool_calls = tool_calls or []
        self.tool_call_index = 0
        self.fail_tools = fail_tools
        self.fail_json = fail_json
        self.system_prompts: list[str] = []

    def _record_system(self, messages: list[dict[str, str]]) -> None:
        for message in messages:
            if message.get("role") == "system" and message.get("content"):
                self.system_prompts.append(str(message["content"]))

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        self._record_system(messages)
        return self.opening

    def chat_stream(self, messages: list[dict[str, str]], **kwargs: Any) -> Any:
        yield self.opening

    def chat_json(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        if self.fail_json:
            raise LLMError("fake llm json failure")
        self._record_system(messages)
        joined = "\n".join(message.get("content") or "" for message in messages)
        if "评分解释" in joined:
            return {
                "score_explanation": "回答覆盖了关键要点，可结合项目证据进一步展开。",
                "fact_hits": ["要点命中"],
                "inference_notes": ["推测性评价"],
                "feedback": "回答完整，可以继续。",
            }
        if self.decisions:
            return self.decisions.pop(0)
        return {
            "action": "next",
            "message": "很好，我们进入下一题。",
            "question_text": "请结合项目经历说明你在项目中负责的模块和解决的问题。",
            "reason": "test decision",
        }

    def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[ToolSpec],
        **kwargs: Any,
    ) -> tuple[str | None, list[Any]]:
        if self.fail_tools:
            raise LLMError("fake llm tool failure")
        self._record_system(messages)
        if self.tool_call_index < len(self.tool_calls):
            call = self.tool_calls[self.tool_call_index]
            self.tool_call_index += 1
            return (None, [call])
        return (None, [])


def as_llm_client(fake: FakeLLMClient) -> LLMClient | None:
    return fake  # type: ignore[return-value]
