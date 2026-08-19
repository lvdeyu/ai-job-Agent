from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from app.models import ModelProviderConfig

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "tongyi": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "claude": "https://api.anthropic.com/v1",
}


class LLMError(RuntimeError):
    pass


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    model_name: str
    base_url: str | None = None
    timeout_seconds: int = 30
    network_mode: str = "auto"
    proxy_url: str | None = None

    @classmethod
    def from_model_provider(cls, config: ModelProviderConfig) -> LLMConfig:
        return cls(
            provider=config.provider,
            api_key=config.api_key,
            model_name=config.model_name,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            network_mode=config.network_mode,
            proxy_url=config.proxy_url,
        )


class LLMClient:
    """Unified LLM gateway for OpenAI-compatible and Anthropic providers."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @property
    def _timeout(self) -> float:
        return float(self.config.timeout_seconds or 30)

    def _http_client(self) -> httpx.Client:
        if self.config.network_mode == "manual_proxy" and self.config.proxy_url:
            return httpx.Client(timeout=self._timeout, proxy=self.config.proxy_url)
        if self.config.network_mode == "direct":
            return httpx.Client(timeout=self._timeout, trust_env=False)
        return httpx.Client(timeout=self._timeout, trust_env=True)

    def _base_url(self) -> str:
        return (
            (self.config.base_url or DEFAULT_BASE_URLS.get(self.config.provider, "https://api.openai.com/v1"))
            .rstrip("/")
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        if self.config.provider == "claude":
            return self._chat_anthropic(messages, max_tokens=max_tokens, temperature=temperature)
        return self._chat_openai_compatible(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        if self.config.provider == "claude":
            yield from self._stream_anthropic(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        else:
            yield from self._stream_openai_compatible(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        content = self.chat(messages, max_tokens=max_tokens, temperature=temperature)
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 2)[1] if "```" in cleaned[3:] else cleaned
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            cleaned = cleaned.rstrip("`").strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM 结构化输出解析失败: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMError("LLM 结构化输出不是 JSON 对象")
        return parsed

    def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[ToolSpec],
        *,
        max_tokens: int = 2048,
    ) -> tuple[str | None, list[ToolCall]]:
        if self.config.provider == "claude":
            return self._tools_anthropic(messages, tools, max_tokens=max_tokens)
        return self._tools_openai_compatible(messages, tools, max_tokens=max_tokens)

    def _chat_openai_compatible(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        with self._http_client() as client:
            try:
                response = client.post(
                    f"{self._base_url()}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                body = response.json()
            except httpx.HTTPError as exc:
                raise LLMError(f"LLM 调用失败: {exc}") from exc
        content = body.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            raise LLMError("LLM 返回空内容")
        return str(content)

    def _stream_openai_compatible(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> Iterator[str]:
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        with self._http_client() as client:
            try:
                with client.stream(
                    "POST",
                    f"{self._base_url()}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        raw = line[len("data:") :].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            chunk = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta:
                            yield str(delta)
            except httpx.HTTPError as exc:
                raise LLMError(f"LLM 流式调用失败: {exc}") from exc

    def _tools_openai_compatible(
        self,
        messages: list[dict[str, str]],
        tools: list[ToolSpec],
        *,
        max_tokens: int,
    ) -> tuple[str | None, list[ToolCall]]:
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ],
        }
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        with self._http_client() as client:
            try:
                response = client.post(
                    f"{self._base_url()}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                body = response.json()
            except httpx.HTTPError as exc:
                raise LLMError(f"LLM 工具调用失败: {exc}") from exc
        message = body.get("choices", [{}])[0].get("message", {})
        content = message.get("content")
        calls: list[ToolCall] = []
        for raw_call in message.get("tool_calls") or []:
            function = raw_call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            calls.append(ToolCall(name=function.get("name") or "", arguments=arguments))
        return (str(content) if content else None, calls)

    def _chat_anthropic(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        payload = {
            "model": self.config.model_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": _anthropic_messages(messages),
        }
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        with self._http_client() as client:
            try:
                response = client.post(
                    f"{self._base_url()}/messages",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                body = response.json()
            except httpx.HTTPError as exc:
                raise LLMError(f"LLM 调用失败: {exc}") from exc
        blocks = body.get("content") or []
        text = "".join(block.get("text") or "" for block in blocks if block.get("type") == "text")
        if not text:
            raise LLMError("LLM 返回空内容")
        return text

    def _stream_anthropic(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> Iterator[str]:
        payload = {
            "model": self.config.model_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "messages": _anthropic_messages(messages),
        }
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        with self._http_client() as client:
            try:
                with client.stream(
                    "POST",
                    f"{self._base_url()}/messages",
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw = line[len("data:") :].strip()
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if event.get("type") == "content_block_delta":
                            delta = (event.get("delta") or {}).get("text")
                            if delta:
                                yield delta
            except httpx.HTTPError as exc:
                raise LLMError(f"LLM 流式调用失败: {exc}") from exc

    def _tools_anthropic(
        self,
        messages: list[dict[str, str]],
        tools: list[ToolSpec],
        *,
        max_tokens: int,
    ) -> tuple[str | None, list[ToolCall]]:
        payload = {
            "model": self.config.model_name,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": _anthropic_messages(messages),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in tools
            ],
        }
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        with self._http_client() as client:
            try:
                response = client.post(
                    f"{self._base_url()}/messages",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                body = response.json()
            except httpx.HTTPError as exc:
                raise LLMError(f"LLM 工具调用失败: {exc}") from exc
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in body.get("content") or []:
            if block.get("type") == "text":
                text_parts.append(block.get("text") or "")
            elif block.get("type") == "tool_use":
                calls.append(
                    ToolCall(
                        name=block.get("name") or "",
                        arguments=block.get("input") or {},
                    )
                )
        content = "".join(text_parts)
        return (content or None, calls)


def _anthropic_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role")
        if role == "system":
            continue
        result.append(
            {
                "role": role if role in {"user", "assistant"} else "user",
                "content": message.get("content", ""),
            }
        )
    if not result:
        result = [{"role": "user", "content": ""}]
    return result
