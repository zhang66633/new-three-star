import httpx
import json
import logging
from typing import AsyncGenerator
from .config import (
    DEEPSEEK_BASE_URL, DEEPSEEK_BETA_URL, DEEPSEEK_MODEL,
    MAX_TOKENS_VERDICT, MAX_TOKENS_WORLDVIEW,
    PARAMS_NARRATIVE, PARAMS_FORMAT, PARAMS_OPTIONS,
)

logger = logging.getLogger(__name__)


async def stream_chat(
    messages: list[dict],
    max_tokens: int = MAX_TOKENS_VERDICT,
    temperature: float | None = None,
    top_p: float | None = None,
    stop: list[str] | None = None,
    prefix: str | None = None,
    api_key: str = "",
) -> AsyncGenerator[str, None]:
    """Stream chat completion from DeepSeek，用玩家自己的 key。

    api_key 由前端通过 X-API-Key 请求头传入——每个玩家用各自的密钥，
    服务端不做兜底（玩家 key 失效就明说，绝不悄悄走部署者的账户）。
    """
    if not api_key:
        yield "[错误] 未配置API密钥——请先回到星图，点击'设置'星球，填入你自己的DeepSeek密钥。"
        return
    try:
        async for chunk in _stream_openai_compatible(
            base_url=DEEPSEEK_BASE_URL,
            beta_url=DEEPSEEK_BETA_URL,
            api_key=api_key,
            model=DEEPSEEK_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop,
            prefix=prefix,
        ):
            yield chunk
    except Exception as e:
        logger.error(f"DeepSeek failed: {e}")
        yield "[错误] API密钥无效或额度不足——请到星图的'设置'星球检查你的密钥。"


async def _stream_openai_compatible(
    base_url: str,
    beta_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float | None = None,
    top_p: float | None = None,
    stop: list[str] | None = None,
    prefix: str | None = None,
) -> AsyncGenerator[str, None]:
    """Call OpenAI-compatible API with streaming.

    v3.2: 完整参数支持 + Chat Prefix Completion。
    注意：prefix 需要 beta endpoint。
    """
    # Chat Prefix Completion：使用 beta endpoint，强制首token
    use_beta = prefix is not None
    url = f"{beta_url if use_beta else base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # 构建消息列表：prefix 模式下在 assistant 消息末尾追加 prefix
    payload_messages = list(messages)
    if prefix:
        payload_messages.append({
            "role": "assistant",
            "content": prefix,
            "prefix": True,
        })

    payload = {
        "model": model,
        "messages": payload_messages,
        "max_tokens": max_tokens,
        "stream": True,
    }

    # temperature 和 top_p：优先传入值，否则用 PARAMS_NARRATIVE 默认
    temp = temperature if temperature is not None else PARAMS_NARRATIVE["temperature"]
    tp = top_p if top_p is not None else PARAMS_NARRATIVE["top_p"]
    payload["temperature"] = temp
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
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
