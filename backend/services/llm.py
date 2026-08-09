import httpx
import json
import logging
from typing import AsyncGenerator
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    HY3_API_KEY, HY3_BASE_URL, HY3_MODEL,
    MAX_TOKENS_VERDICT,
    PARAMS_NARRATIVE,
)

logger = logging.getLogger(__name__)


async def stream_chat(
    messages: list[dict],
    max_tokens: int = MAX_TOKENS_VERDICT,
    temperature: float | None = None,
    top_p: float | None = None,
    stop: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat completion from DeepSeek, fallback to Hy3.

    v3.2 更新：
    - 移除 frequency_penalty/presence_penalty（V4 不支持）
    - temperature 提升至 1.3（官方创意写作推荐 1.5）
    - 新增 stop 序列支持
    """
    try:
        async for chunk in _stream_openai_compatible(
            base_url=DEEPSEEK_BASE_URL,
            api_key=DEEPSEEK_API_KEY,
            model=DEEPSEEK_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop,
        ):
            yield chunk
    except Exception as e:
        logger.error(f"DeepSeek failed: {e}, trying fallback...")
        if HY3_API_KEY and HY3_BASE_URL:
            try:
                async for chunk in _stream_openai_compatible(
                    base_url=HY3_BASE_URL,
                    api_key=HY3_API_KEY,
                    model=HY3_MODEL,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop=stop,
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
    temperature: float | None = None,
    top_p: float | None = None,
    stop: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """Call OpenAI-compatible API with streaming."""
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload_messages = list(messages)

    payload = {
        "model": model,
        "messages": payload_messages,
        "max_tokens": max_tokens,
        "stream": True,
        "thinking": {"type": "disabled"},  # V4 Pro 默认推理模式，必须显式关闭
    }

    # temperature 和 top_p：优先传入值，否则用 PARAMS_NARRATIVE 默认
    temp = temperature if temperature is not None else PARAMS_NARRATIVE.get("temperature", 1.3)
    tp = top_p if top_p is not None else PARAMS_NARRATIVE.get("top_p", 1.0)
    payload["temperature"] = temp
    if tp is not None:
        payload["top_p"] = tp

    if stop:
        payload["stop"] = stop

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
                    # V4 Pro 推理模式：content 在 reasoning 结束后才出现
                    content = delta.get("content", "")
                    # 如果 content 为 null，跳过（reasoning_content 阶段）
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
