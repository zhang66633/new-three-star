# -*- coding: utf-8 -*-
"""
Remember（记忆节点 · STM/LTM/PIN 三层）
========================================
依据: docs/引擎设计规范.md §4

- STM: ≤6 条 × 50-80 字（当前场景客观事实），满 6 晋升 LTM
- LTM: 无上限 × 120-150 字（LLM 压缩生成）
- PIN: ≤5 条（玩家手动钉选，永不压缩，检索优先）
- 检索: PIN 全部 + top5 LTM + 当前 STM（TF-IDF 向量排名 + 关键词/时效排名，RRF 融合，见 services/rag.py）
- 索引: 每次 LTM 变更全量重建（记忆量小，成本可接受）
"""
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

STM_CAP = 8          # 扩容（原 6）：压缩失败时留缓冲，防满 6 后 stm_append 截断静默丢旧事实
COMPRESS_AT = 6        # 满 6 条即触发晋升（低于 STM_CAP，留 2 条缓冲兜底）
RETRIEVE_LTM_TOP = 5
LTM_CAP = 40           # 长期记忆软上限：超过则最旧若干条二次合并（防 JSON 回传随时长无限膨胀）

COMPRESS_PROMPT = """把以下 {n} 条短期记忆压缩为 1 条长期记忆（120-150 字）。
要求（信息密度优先，宁全勿漏）：
- 合并重复信息，保留关键事实（谁/何时/何地/何事/后果）
- 客观陈述，不添加主观评价
- 【铁律】绝不可丢失：与具体人物的关系变化、未兑现的承诺/约定、伏笔、玩家未竟目标、
  玩家拥有/失去的重要物品、生死信息——这些即使字数紧张也要保留一句
- 文本开头嵌入时间场景上下文（如"光和七年·颍川雨夜：……"）

【短期记忆】
{stm_text}

【输出】严格 JSON 数组: ["..."]（只输出 1 条）""".strip()


CONSOLIDATE_PROMPT = """把以下 {n} 条较早的长期记忆合并为 1 条（120-150 字），做记忆巩固与遗忘：
- 保留：与具体人物的关系、未兑现的承诺、伏笔、玩家身份/称号、生死信息、关键因果
- 丢弃：已过时的环境描写、可再生的细节、重复的铺垫
- 客观陈述，时间场景上下文嵌入开头

【较早的长期记忆】
{ltm_text}

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
    mem["stm"] = stm[-STM_CAP:]  # 超上限截断（STM_CAP=8，留压缩失败缓冲）
    state["memory"] = mem
    return state


async def promote_stm_to_ltm(state: dict) -> dict:
    """STM 满 6 条 → LLM 压缩 → LTM + 清 STM"""
    mem = state.get("memory", {})
    stm = mem.get("stm", [])
    if len(stm) < COMPRESS_AT:
        return state

    from services.llm import stream_chat
    from config import PARAMS_FORMAT, STOP_SEQUENCES, QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL

    # 收集 STM 条目的场景标签（供 LTM 条目继承）
    stm_scenes = [s.get("scene", "") for s in stm if s.get("scene")]
    scene_ctx = "、".join(stm_scenes[:3]) if stm_scenes else ""
    stm_text = "\n".join(f"{i+1}. [{s.get('scene', '?')}] {s['text']}" for i, s in enumerate(stm))
    prompt = COMPRESS_PROMPT.format(n=len(stm), stm_text=stm_text)
    messages = [
        {"role": "system", "content": "你是记忆整理器，输出严格 JSON 数组。"},
        {"role": "user", "content": prompt},
    ]
    # 双模型试验：记忆压缩（主控）走 Qwen；key 由 stream_chat 解析
    raw = ""
    _ctrl = dict(base_url=QWEN_BASE_URL, model=QWEN_MODEL)
    async for chunk in stream_chat(messages, max_tokens=1024, **PARAMS_FORMAT, stop=STOP_SEQUENCES, **_ctrl):
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
    # 记忆巩固 + 遗忘衰败（技术 14/15/19）：LTM 超软上限 → 最旧若干条二次合并
    if len(ltm) > LTM_CAP:
        state = await _consolidate_ltm(state)
    return state


async def _consolidate_ltm(state: dict) -> dict:
    """LTM 超软上限（LTM_CAP=40）→ 最旧 10 条合并为 1 条。

    对应「记忆巩固 + 内存压缩 + 遗忘衰败」：把久远的环境细节压掉、保留
    关系/承诺/伏笔/身份等长期关键，防 JSON 回传体积随时长无限膨胀。
    低频（约 240 拍触发一次），额外 LLM 调用成本可接受。
    """
    mem = state.get("memory", {})
    ltm = list(mem.get("ltm", []))
    if len(ltm) <= LTM_CAP:
        return state

    from services.llm import stream_chat
    from config import PARAMS_FORMAT, STOP_SEQUENCES, QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL

    old = ltm[:10]
    rest = ltm[10:]
    ltm_text = "\n".join(f"{i+1}. {m['text']}" for i, m in enumerate(old))
    prompt = CONSOLIDATE_PROMPT.format(n=len(old), ltm_text=ltm_text)
    messages = [
        {"role": "system", "content": "你是记忆整理器，输出严格 JSON 数组。"},
        {"role": "user", "content": prompt},
    ]
    raw = ""
    _ctrl = dict(base_url=QWEN_BASE_URL, model=QWEN_MODEL)
    async for chunk in stream_chat(messages, max_tokens=1024, **PARAMS_FORMAT, stop=STOP_SEQUENCES, **_ctrl):
        raw += chunk

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
    if not items:
        logger.warning("LTM 二次合并失败（压缩空/解析失败），保留现状")
        return state

    ts = state.get("turn", 0)
    merged = {"id": _new_id(items[0], ts), "text": items[0], "ts": ts}
    mem["ltm"] = [merged] + rest
    state["memory"] = mem
    logger.info(f"LTM 二次合并：最旧 {len(old)} 条 → 1 条（剩 {len(mem['ltm'])} 条）")
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
    """LTM 检索：TF-IDF 向量排名 与 关键词/时效排名 经 RRF 融合，取 top_k（见 services/rag.py）。"""
    from services.rag import retrieve_ltm
    return retrieve_ltm(ltm, query, top_k=top_k)
