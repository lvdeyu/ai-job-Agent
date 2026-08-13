from __future__ import annotations

import httpx

from app.models import ModelProviderConfig

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "tongyi": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "claude": "https://api.anthropic.com/v1",
}
DEEPSEEK_ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"


async def test_model_connection(config: ModelProviderConfig) -> tuple[bool, str, str | None]:
    if config.api_key.startswith("sk-local-test"):
        return True, "本地测试密钥已通过格式检查，未发起真实外部请求。", None

    if config.provider == "deepseek" and _is_deepseek_anthropic_url(config.base_url):
        return (
            False,
            "当前 DeepSeek 连接测试使用 OpenAI 兼容接口，请把 Base URL 改为 "
            "https://api.deepseek.com；/anthropic 属于 Anthropic 兼容接口，后续再单独适配。",
            "UNSUPPORTED_BASE_URL",
        )

    try:
        if config.provider == "claude":
            return await _test_claude(config)
        return await _test_openai_compatible(config)
    except httpx.TimeoutException:
        return False, "AI 连接测试超时，请检查网络、Base URL 或超时时间。", "TIMEOUT"
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            return False, "认证失败，请检查 API Key。", "AUTH_FAILED"
        if exc.response.status_code == 404:
            return False, "模型或接口不存在，请检查模型名称和 Base URL。", "MODEL_NOT_FOUND"
        return False, f"供应商返回 HTTP {exc.response.status_code}。", "HTTP_ERROR"
    except httpx.RequestError:
        if config.network_mode == "direct":
            return (
                False,
                "直连模型供应商失败，请检查网络、DNS、防火墙或切换为自动/手动代理。",
                "NETWORK_ERROR",
            )
        if config.network_mode == "manual_proxy":
            return (
                False,
                "通过手动代理连接失败，请检查代理地址是否正确、代理软件是否运行。",
                "PROXY_ERROR",
            )
        return (
            False,
            "无法连接到模型供应商，请检查网络、Base URL，或尝试手动配置代理。",
            "NETWORK_ERROR",
        )


def _is_deepseek_anthropic_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    return base_url.rstrip("/").lower() == DEEPSEEK_ANTHROPIC_BASE_URL


async def _test_openai_compatible(config: ModelProviderConfig) -> tuple[bool, str, str | None]:
    base_url = (config.base_url or DEFAULT_BASE_URLS[config.provider]).rstrip("/")
    payload = {
        "model": config.model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    headers = {"Authorization": f"Bearer {config.api_key}"}
    async with _build_http_client(config) as client:
        response = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
    return True, "AI 连接测试成功。", None


async def _test_claude(config: ModelProviderConfig) -> tuple[bool, str, str | None]:
    base_url = (config.base_url or DEFAULT_BASE_URLS[config.provider]).rstrip("/")
    payload = {
        "model": config.model_name,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    async with _build_http_client(config) as client:
        response = await client.post(f"{base_url}/messages", json=payload, headers=headers)
        response.raise_for_status()
    return True, "AI 连接测试成功。", None


def _build_http_client(config: ModelProviderConfig) -> httpx.AsyncClient:
    if config.network_mode == "manual_proxy" and config.proxy_url:
        return httpx.AsyncClient(timeout=config.timeout_seconds, proxy=config.proxy_url)
    if config.network_mode == "direct":
        return httpx.AsyncClient(timeout=config.timeout_seconds, trust_env=False)
    return httpx.AsyncClient(timeout=config.timeout_seconds, trust_env=True)
