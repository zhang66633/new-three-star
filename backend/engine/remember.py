# -*- coding: utf-8 -*-
"""
Remember（记忆节点 · STM/LTM/PIN 三层）
========================================
依据: docs/引擎设计规范.md §4

- STM: ≤6 条 × 50-80 字（当前场景客观事实），满 6 晋升 LTM
- LTM: 无上限 × 120-150 字（LLM 压缩生成）
- PIN: ≤5 条（玩家手动钉选，永不压缩，检索优先）
- 检索: PIN 全部 + top5 LTM + 当前 STM（关键词重叠 + 时效打分，见 _retrieve_ltm）
  —— 注：未复用 services/rag.py（rag 面向知识库素材检索，非 LTM 记忆）
- 索引: 每次 LTM 变更全量重建（记忆量小，成本可接受）
"""
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

STM_CAP = 6
RETRIEVE_LTM_TOP = 5

COMPRESS_PROMPT = """把以下 {n} 条短期记忆压缩为 1 条长期记忆（120-150 字）。
要求：
- 合并重复信息，保留关键事实（谁/何时/何地/何事/后果）
- 客观陈述，不添加主观评价
- 保留与玩家的关系、承诺、伏笔
- 文本开头嵌入时间场景上下文（如"光和七年·颍川雨夜：……"）

【短期记忆】
{stm_text}

【输出】严格 JSON 数组: ["..."]（只输出 1 条）""".strip()


# ═════════ 基础操作 ═════════

def _new_id(text: str, ts: int) -> str:
    # ts 含轮次与序号（防同轮同文本重复）
    return hashlib.md5(f"{ts}:{text[:30]}:{hash(text) % 100000}".encode()).hexdigest()[:8]


def stm_append(state: dict, entry: str, scene_label: str = "", time_label: str = "") -> dict:
    """STM 追加一条（返回更新后的 state）

    scene_label: 可选场景标记（如 "颍川·雨夜荒野"），前端记忆抽屉用。
    time_label:  可读时间标记（如 "光和七年·春"），前端记忆抽屉用。
    """
    mem = state.get("memory", {})
    stm = list(mem.get("stm", []))
    ts = state.get("turn", 0)
    item = {"id": _new_id(entry, ts), "text": entry[:80], "ts": ts}
    # 文本级去重：同一条事实不重复入 STM（id 哈希含 ts，跨轮同文本无法靠 id 去重，
    # 如 P1_s1 开局+续场会重复写入同条记忆）
    if any(m.get("text") == item["text"] for m in stm):
        return state
    if scene_label:
        item["scene"] = scene_label
    if time_label:
        item["time"] = time_label
    stm.append(item)
    mem["stm"] = stm[-STM_CAP:]  # 超上限截断
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

    # 收集 STM 条目的场景标签（供 LTM 条目继承）
    stm_scenes = [s.get("scene", "") for s in stm if s.get("scene")]
    scene_ctx = "、".join(stm_scenes[:3]) if stm_scenes else ""
    stm_text = "\n".join(f"{i+1}. [{s.get('scene', '?')}] {s['text']}" for i, s in enumerate(stm))
    prompt = COMPRESS_PROMPT.format(n=len(stm), stm_text=stm_text)
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

    # 压缩失败/解析空：不丢 STM，保留下轮重试（防静默数据丢失）
    if not items:
        logger.warning(f"记忆晋升失败（压缩结果空/解析失败），保留 STM {len(stm)} 条待下轮重试")
        return state

    ltm = list(mem.get("ltm", []))
    ts = state.get("turn", 0)
    for item in items:
        entry = {"id": _new_id(item, ts), "text": item, "ts": ts}
        if scene_ctx:
            entry["scene"] = scene_ctx
        ltm.append(entry)
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
    """LTM 检索：关键词重叠 + 时效性混合打分，取 top_k 条。

    评分：关键词命中 ×1.5 + 时效衰减（越新越高）。
    不依赖 rag 索引（rag 面向知识库，非 LTM 记忆）。
    """
    if not ltm:
        return []

    # 1. 查询关键词（2-4 字滑窗取词，去重）
    query_clean = query.replace("，", "").replace("。", "").replace(" ", "")
    keywords = set()
    for wlen in (2, 3, 4):
        for i in range(len(query_clean) - wlen + 1):
            w = query_clean[i:i + wlen]
            if w.strip():
                keywords.add(w)

    if not keywords:
        return sorted(ltm, key=lambda m: m.get("ts", 0), reverse=True)[:top_k]

    # 2. 打分
    max_ts = max((m.get("ts", 0) for m in ltm), default=1)

    def score(m: dict) -> float:
        text = m.get("text", "")
        hits = sum(1 for kw in keywords if kw in text)
        recency = m.get("ts", 0) / max(max_ts, 1)  # 0-1，越近越高
        return hits * 1.5 + recency * 0.5

    scored = sorted(ltm, key=score, reverse=True)
    # 过滤掉 0 分（完全不相关）的条目
    relevant = [m for m in scored if score(m) > 0]

    return (relevant or scored)[:top_k]
