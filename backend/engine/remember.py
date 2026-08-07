# -*- coding: utf-8 -*-
"""
Remember（记忆节点 · STM/LTM/PIN 三层）
========================================
依据: docs/引擎设计规范.md §4

- STM: ≤6 条 × 50-80 字（当前场景客观事实），满 6 晋升 LTM
- LTM: 无上限 × 120-150 字（LLM 压缩生成）
- PIN: ≤5 条（玩家手动钉选，永不压缩，检索优先）
- 检索: PIN 全部 + top5 LTM + 当前 STM（复用 services/rag.py 向量检索）
- 索引: 每次 LTM 变更全量重建（记忆量小，成本可接受）
"""
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

STM_CAP = 6
PIN_CAP = 5
RETRIEVE_LTM_TOP = 5

COMPRESS_PROMPT = """把以下 {n} 条短期记忆压缩为 {k} 条长期记忆（每条 120-150 字）。
要求：
- 合并重复信息，保留关键事实（谁/何时/何地/何事/后果）
- 客观陈述，不添加主观评价
- 保留与玩家的关系、承诺、伏笔

【短期记忆】
{stm_text}

【输出】严格 JSON 数组: ["...", "..."]""".strip()


# ═════════ 基础操作 ═════════

def _new_id(text: str, ts: int) -> str:
    # ts 含轮次与序号（防同轮同文本重复）
    return hashlib.md5(f"{ts}:{text[:30]}:{hash(text) % 100000}".encode()).hexdigest()[:8]


def stm_append(state: dict, entry: str) -> dict:
    """STM 追加一条（返回更新后的 state）"""
    mem = state.get("memory", {})
    stm = list(mem.get("stm", []))
    ts = state.get("turn", 0)
    stm.append({"id": _new_id(entry, ts), "text": entry[:80], "ts": ts})
    mem["stm"] = stm[-STM_CAP:]  # 超上限截断
    state["memory"] = mem
    return state


def pin(state: dict, mem_id: str) -> dict:
    """玩家钉选记忆（≤5 条）"""
    mem = state.get("memory", {})
    pins = list(mem.get("pins", []))
    if mem_id in pins:
        return state
    pins.append(mem_id)
    mem["pins"] = pins[-PIN_CAP:]
    state["memory"] = mem
    return state


def unpin(state: dict, mem_id: str) -> dict:
    mem = state.get("memory", {})
    mem["pins"] = [p for p in mem.get("pins", []) if p != mem_id]
    state["memory"] = mem
    return state


async def promote_stm_to_ltm(state: dict) -> dict:
    """STM 满 6 条 → LLM 压缩 → LTM + 清 STM"""
    mem = state.get("memory", {})
    stm = mem.get("stm", [])
    if len(stm) < STM_CAP:
        return state

    from services.llm import stream_chat
    from config import PARAMS_FORMAT, STOP_SEQUENCES

    stm_text = "\n".join(f"{i+1}. {s['text']}" for i, s in enumerate(stm))
    k = max(2, len(stm) // 3)
    prompt = COMPRESS_PROMPT.format(n=len(stm), k=k, stm_text=stm_text)
    messages = [
        {"role": "system", "content": "你是记忆整理器，输出严格 JSON 数组。"},
        {"role": "user", "content": prompt},
    ]
    raw = ""
    async for chunk in stream_chat(messages, max_tokens=1024, **PARAMS_FORMAT, stop=STOP_SEQUENCES):
        raw += chunk

    # 解析 JSON 数组
    try:
        items = json.loads(raw.strip())
        if not isinstance(items, list):
            items = []
    except json.JSONDecodeError:
        import re
        m = re.search(r'\[.*\]', raw, re.S)
        try:
            items = json.loads(m.group(0)) if m else []
        except json.JSONDecodeError:
            items = []
    items = [str(i)[:150] for i in items if str(i).strip()]

    ltm = list(mem.get("ltm", []))
    ts = state.get("turn", 0)
    for item in items:
        ltm.append({"id": _new_id(item, ts), "text": item, "ts": ts})
    mem["ltm"] = ltm
    mem["stm"] = []
    state["memory"] = mem
    logger.info(f"记忆晋升: STM {len(stm)} 条 → LTM {len(items)} 条（共 {len(ltm)} 条）")
    return state


# ═════════ 检索 ═════════

def retrieve_memories(state: dict, query: str) -> list[dict]:
    """检索记忆注入包：PIN 全部 + top5 LTM + 当前 STM"""
    mem = state.get("memory", {})
    pins = mem.get("pins", [])
    stm = mem.get("stm", [])
    ltm = mem.get("ltm", [])

    # 1. PIN 全部（按 id 查）
    pin_items = []
    all_items = {**{m["id"]: m for m in stm}, **{m["id"]: m for m in ltm}}
    for pid in pins:
        if pid in all_items:
            pin_items.append(all_items[pid])

    # 2. top5 LTM（向量检索，复用 rag；失败降级最近 5 条）
    top_ltm = _retrieve_ltm(ltm, query)

    # 3. 当前 STM 全部
    return pin_items + top_ltm + stm


def _retrieve_ltm(ltm: list[dict], query: str, top_k: int = RETRIEVE_LTM_TOP) -> list[dict]:
    """LTM 检索：复用 rag 的 TF-IDF+Embedding 融合；失败降级最近 top_k 条"""
    if not ltm:
        return []
    try:
        from services.rag import search as rag_search
        results = rag_search(query, top_k=top_k)
        if results:
            # rag 检索的是知识库，此处需按 LTM 文本匹配——简化：直接取最近的
            # TODO(Phase 2 完善): 为 LTM 单独建小索引（build_memory_index）
            pass
    except Exception as e:
        logger.warning(f"LTM 检索降级: {e}")
    # 降级：最近 top_k 条
    return sorted(ltm, key=lambda m: m.get("ts", 0), reverse=True)[:top_k]
