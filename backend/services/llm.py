import httpx
import json
import logging
import contextvars
from typing import AsyncGenerator
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    QWEN_MODEL,
    MAX_TOKENS_VERDICT,
    PARAMS_NARRATIVE,
)

logger = logging.getLogger(__name__)

# BYOK：玩家自带的 DeepSeek 密钥（X-API-Key 请求头）经请求级 ContextVar 传递，
# 让 LangGraph 引擎各节点（narrate/validate/corrector/remember）无需改签名即可读到。
_api_key_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("api_key", default="")
# 双模型试验：Qwen 主控密钥（X-QWEN-API-Key 请求头）——玩家可选，未填则主控回退 DeepSeek
_qwen_key_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("qwen_api_key", default="")
# DeepSeek 模型选择（X-DEEPSEEK-MODEL 请求头）：玩家可切换 flash/v4-pro 等，默认 deepseek-v4-flash
_model_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("deepseek_model", default="")
# Qwen 模型选择（X-QWEN-MODEL 请求头）：玩家可切换 35b-a3b/plus/27b 等，默认 qwen3.5-35b-a3b
_qwen_model_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("qwen_model", default="")


def set_api_key(key: str) -> None:
    """请求处理器在进入引擎前设置；空串 → stream_chat 按严格 BYOK 报错。"""
    _api_key_ctx.set(key.strip() if key else "")


def set_qwen_api_key(key: str) -> None:
    """双模型试验：设置玩家 Qwen 主控密钥（空串=未配置，主控回退 DeepSeek）。"""
    _qwen_key_ctx.set(key.strip() if key else "")


def set_deepseek_model(model: str) -> None:
    """设置玩家选择的 DeepSeek 模型名（空串=用 .env 默认）。"""
    _model_ctx.set(model.strip() if model else "")


def set_qwen_model(model: str) -> None:
    """双模型试验：设置玩家选择的 Qwen 主控模型名（空串=用 .env 默认）。"""
    _qwen_model_ctx.set(model.strip() if model else "")


async def stream_chat(
    messages: list[dict],
    max_tokens: int = MAX_TOKENS_VERDICT,
    temperature: float | None = None,
    top_p: float | None = None,
    stop: list[str] | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream chat completion.

    双模型路由（experiment/dual-model）：
      - 默认（base_url/model 缺省）→ DeepSeek（叙事 writer 用）
      - 传 base_url/model → 指定模型（validator/corrector 主控用 Qwen3.5）
    未配置 QWEN_API_KEY 时，主控调用自动回退 DeepSeek（单模型模式，线上不受影响）。

    BYOK：api_key 缺省时读请求级 ContextVar（play.py 从 X-API-Key 头设置）。
    严格不兑底——玩家不填 key 就明说，绝不悄悄走服务器账户（服务器 key 仅供
    RAG embedding 等系统内部用，不承接玩家叙事）。
    """
    # 双模型试验：主控调用（显式传了 base_url/model）优先用请求级 Qwen key；
    # 无 Qwen key 时回退 DeepSeek key（单模型模式）。叙事调用（无 base_url/model）恒用 DeepSeek key。
    is_ctrl = bool(base_url or model)
    qwen_key_ctx = _qwen_key_ctx.get()
    if is_ctrl and (qwen_key_ctx or api_key):
        key = api_key if api_key else qwen_key_ctx
        missing_hint = "Qwen 密钥"
    else:
        key = api_key if api_key else _api_key_ctx.get()
        missing_hint = "DeepSeek 密钥"
    if not key:
        yield f"[错误] 未配置API密钥——请先到星图的'设置'星球，填入你自己的{missing_hint}。"
        return
    # DeepSeek 模型：玩家请求头选择优先（X-DEEPSEEK-MODEL），未选回退 .env 默认
    _model = model
    if not _model and not is_ctrl:
        _model = _model_ctx.get() or DEEPSEEK_MODEL
    elif not _model and is_ctrl:
        # Qwen 主控模型：玩家选择优先（X-QWEN-MODEL），未选回退 .env QWEN_MODEL
        _model = _qwen_model_ctx.get() or QWEN_MODEL
    try:
        async for chunk in _stream_openai_compatible(
            base_url=base_url or DEEPSEEK_BASE_URL,
            api_key=key,
            model=_model or DEEPSEEK_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop,
        ):
            yield chunk
    except Exception as e:
        # 主控调用（Qwen）失败 → 自动回退 DeepSeek 重试一次（玩家体验不受损）
        # 叙事调用（DeepSeek）失败 → 直接报错（严格 BYOK 不兑底）
        if is_ctrl:
            logger.warning(f"Qwen 主控调用失败，回退 DeepSeek: {e}")
            try:
                async for chunk in _stream_openai_compatible(
                    base_url=DEEPSEEK_BASE_URL,
                    api_key=_api_key_ctx.get(),
                    model=_model_ctx.get() or DEEPSEEK_MODEL,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop=stop,
                ):
                    yield chunk
                return
            except Exception as e2:
                logger.error(f"DeepSeek 回退也失败: {e2}")
        else:
            logger.error(f"LLM ({model or DEEPSEEK_MODEL}) failed: {e}")
        yield "[错误] API密钥无效或额度不足——请到星图的'设置'星球检查你的密钥。"


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
    }
    # DeepSeek V4 Pro 默认推理模式必须显式关闭；Qwen 等 OpenAI 兼容端点不认该参数
    if "deepseek" in base_url.lower():
        payload["thinking"] = {"type": "disabled"}

    # temperature 和 top_p：优先传入值，否则用 PARAMS_NARRATIVE 默认
    temp = temperature if temperature is not None else PARAMS_NARRATIVE.get("temperature", 1.3)
    tp = top_p if top_p is not None else PARAMS_NARRATIVE.get("top_p", 1.0)
    payload["temperature"] = temp
    if tp is not None:
        payload["top_p"] = tp

    if stop:
        payload["stop"] = stop

    async with httpx.AsyncClient(timeout=300.0) as client:
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
