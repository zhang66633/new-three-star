import httpx
import json
import logging
from typing import AsyncGenerator
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    HY3_API_KEY, HY3_BASE_URL, HY3_MODEL,
    MAX_TOKENS_VERDICT, MAX_TOKENS_WORLDVIEW, TEMPERATURE,
)

logger = logging.getLogger(__name__)


async def stream_chat(
    messages: list[dict],
    max_tokens: int = MAX_TOKENS_VERDICT,
) -> AsyncGenerator[str, None]:
    """Stream chat completion from DeepSeek, fallback to Hy3."""
    try:
        async for chunk in _stream_openai_compatible(
            base_url=DEEPSEEK_BASE_URL,
            api_key=DEEPSEEK_API_KEY,
            model=DEEPSEEK_MODEL,
            messages=messages,
            max_tokens=max_tokens,
        ):
            yield chunk
    except Exception as e:
        logger.error(f"DeepSeek failed: {e}, trying fallback...")
        # Fallback to Hy3
        if HY3_API_KEY and HY3_BASE_URL:
            try:
                async for chunk in _stream_openai_compatible(
                    base_url=HY3_BASE_URL,
                    api_key=HY3_API_KEY,
                    model=HY3_MODEL,
                    messages=messages,
                    max_tokens=max_tokens,
                ):
                    yield chunk
            except Exception as e2:
                logger.error(f"Hy3 fallback also failed: {e2}")
                yield "[错误] LLM服务不可用，请稍后重试。"
        else:
            yield "[错误] LLM服务不可用，请稍后重试。"


async def _stream_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    max_tokens: int,
) -> AsyncGenerator[str, None]:
    """Call OpenAI-compatible API with streaming."""
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": TEMPERATURE,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                raise Exception(f"LLM API error: {resp.status_code}")
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta = data["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
