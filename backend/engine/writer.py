# -*- coding: utf-8 -*-
"""
Writer（编剧层 · 唯一 LLM 生成调用）
====================================
职责：根据 ScenePlan + State → 生成 NarrativeOutput（叙事 + 选项 + state_updates）
要点：
- 人设分层注入（远观=轻量 / 互动=完整人设卡 / 核心=完整+专属机制）
- 世界侧零提示铁律（prompt 明文）
- 后处理：services.validator 确定性修复 + services.deslop 去AI味
"""
import json
import logging
import os

from .state import GameState
from .director import ScenePlan

logger = logging.getLogger(__name__)

# 已知角色名（供 director 距离映射 / validator 白名单）
KNOWN_NAMES = {
    "曹操", "刘备", "关羽", "张飞", "诸葛亮", "司马懿", "吕布", "董卓", "袁绍",
    "袁术", "孙权", "周瑜", "陈宫", "王允", "貂蝉", "赵云", "马超", "黄忠",
    "魏延", "庞统", "姜维", "鲁肃", "吕蒙", "陆逊", "张角", "张宝", "张梁",
    "华雄", "颜良", "文丑", "邢道荣", "许攸", "蔡瑁", "徐庶", "法正", "孙坚",
    "孙策", "吕伯奢", "汉献帝", "小黄门", "黄金兵", "老者", "黑影", "乡绅",
}

# 人设分层注入（决策 8）
PERSONA_LIGHT = {
    "曹操": "曹操：枭雄，心思深沉。",
    "刘备": "刘备：仁义之君，喜怒不形于色。",
    "关羽": "关羽：傲慢武圣，重义。",
    "张飞": "张飞：暴躁猛将，性如烈火。",
    "诸葛亮": "诸葛亮：旷世奇才，运筹帷幄。",
    "司马懿": "司马懿：隐忍老谋，深不可测。",
    "吕布": "吕布：武艺无双，心思单纯。",
    "董卓": "董卓：残暴权臣，视天子为掌中物。",
    "袁绍": "袁绍：名门之后，优柔寡断。",
    "张角": "张角：黄金军首领，被天意吞噬后神智不清。",
    "张宝": "张宝：张角之弟，黄金军将领，暴戾好战。",
    "张梁": "张梁：张角之弟，黄金军将领，谨慎多疑。",
    "汉献帝": "汉献帝：傀儡天子，年幼无助。",
    "陈宫": "陈宫：谋士，刚直不阿。",
    "吕伯奢": "吕伯奢：成皋吕家寨大当家，好客重情。",
    "孙权": "孙权：少年英主，善于用人。",
    "周瑜": "周瑜：儒将，才华横溢。",
    "赵云": "赵云：忠勇无双，白马银枪。",
    "孙坚": "孙坚：江东猛虎，勇猛果敢。",
    "老者": "老者：颍川乡民，见多识广，语带玄机。",
    "黑影": "黑影：逃难路人，警惕慌张。",
    "乡绅": "乡绅：颍川本地富户，精于算计。",
    "黄金兵": "黄金兵：黄金军底层士兵，多为被裹挟的流民。",
}

PERSONA_FULL = {
    "曹操": "曹操：枭雄，窥探天意被侵蚀。清醒时雄才大略，压力下失态。名场面'宁可我负天下人'。",
    "刘备": "刘备：仁义面具+内心盘算。哭是真哭，算计也是真算计。'自刎归天'口头禅。",
    "关羽": "关羽：傲慢武圣。摸须装逼，'龙是帝王之征'。水淹七军。",
    "诸葛亮": "诸葛亮：天才+受气包。被关张欺负，向马谡甩锅。窥探天意最深处被侵蚀。",
    "司马懿": "司马懿：隐忍老狐狸。话少看透一切，视他人为NPC。",
    "吕布": "吕布：率真莽夫。武力+100%智力-250%，'为何我是三姓家奴'。",
    "董卓": "董卓：大汉忠臣（自认）。视刘协为唯一亲人，'咱家'自称。",
    "袁绍": "袁绍：宽厚明主。众望所归却屡失良机，'死亡抗性II'。",
    "张角": "张角：被天意吞噬的教主。清醒时悲天悯人，混沌时狂言呓语。黄金军已偏离其初衷。",
    "张宝": "张宝：张角之弟。嗜血好杀，视百姓为草芥。对兄长的疯癫深感不安但无法反抗。",
    "陈宫": "陈宫：刚直谋士。弃曹操投吕布，一生忠于理想。擅长看穿人心但拙于自保。",
    "吕伯奢": "吕伯奢：成皋吕家寨大当家，占山为王的匪首与慈祥长辈一体，急公好义又粗豪。视曹操为旧友，杀猪宰鹅温酒设宴热情相待——被误杀时，死于自己的一片好心。",
    "孙权": "孙权：少年继位，天生政治家。表面从谏如流，内心深不可测。'生子当如孙仲谋'。",
    "周瑜": "周瑜：儒将，雅量高致。既生瑜何生亮。对孙策之死耿耿于怀。",
    "赵云": "赵云：忠勇无双。不争功不夺利，真正的'完美武将'。内心对乱世有深沉的悲悯。",
    "老者": "老者：颍川荒野中的神秘老人。语带玄机，似乎知道更多。可能是天意的观察者。",
}

# 世界底色（注入 system）
WORLD_BASE = """
【世界】这是一个由蹩脚 AI 生成的三国世界。
- 世界外观是正常的三国（人物、地名、历史大势与史书/演义基本一致）
- 但生成者是蹩脚的：时间会跳接、NPC 记忆会覆盖、巧合会堆叠、修正会留痕
- 世界从不解释这些异常。NPC 会用"世界自己的逻辑"把它们合理化
- 没有人察觉世界不对劲——除了玩家

【玩家】玩家是偶然落入此世的"无名奇人"：
- 无来历、无户籍、查无此人；没有机制为"查无此人"提供预案，所以世界默认接纳他
- 玩家知道"大概的历史走向"（似曾相识的直觉），但细节模糊、时代错乱
- 玩家说出预言：应验则"言多中验"，声望大涨；频频预言则被视为狂人
- 玩家不能使用现代词汇/知识解释世界（会被当作疯子，除非不解释）

【铁律】
1. 绝不出现 meta 语言：不出现"系统/AI/世界是假的/你在游戏中/穿越者"等字样；玩家内心也不得把"穿越者"当确定事实向世界宣告
2. 绝不出现"点明不对劲"的提示：严禁'没人觉得不对''无人察觉''世界似乎……'等任何宣告集体无觉察的全知旁白——世界完全正常地演出，玩家自己察觉差异；玩家内心可写"你记得史书上写的是黄巾"，但不得写"没有人觉得这是黄巾"
3. 世界漏洞只通过玩家视角呈现：玩家用自己的认知对比发现偏差（如知道"黄巾"却看到"黄金"）——但世界侧一切正常，NPC 永不讨论这些偏差
4. NPC 对玩家来历从不过问，正常对话自然接纳
5. 历史大势不可推翻，但修正留痕且过程可被改写
6. 玩家的关系、声望、记忆永远生效
7. 输出为叙事文本 + 2-3 个选项；选项须是"少而重大"的道德两难或行动抉择
8. 选项 text/effect 严禁 meta 词与现代词出口给 NPC（如"穿越者""现代""剧本"）；玩家向 NPC 说出异常认知时，NPC 以世界逻辑自然接住或当他疯话
""".strip()

# 叙事生成指令
WRITER_INSTRUCTION = """
【当前场景】{chapter_label} · {title}
【场景设定】{setting}
【世界侧正常演出】{world_normal}
【玩家视角差异（仅玩家可感知，世界侧不讨论）】{player_pov}
【锁定台词（必须逐字出现，说话人标注）】{locked_lines}
【在场角色人设】{personas}

【输出要求】
1. 生成 600-1000 字叙事正文（第二人称"你"），描写当前场景
2. 玩家视角差异通过玩家内心/观察自然呈现（如：你记得史书上写的是'黄巾'……），但世界侧一切正常
3. 基调"轻松网文"：语言利落、节奏明快，多用短句短段；画面感保留，但忌堆叠比喻意象、忌抒情长句、忌过度蒙太奇；说人话
4. 叙事语气带乐子人的轻盈——即使场景沉重（雨夜/杀戮/悲剧），叙述也不煽情不压抑，保持轻快的看戏感
5. 感官细节覆盖至少两类（视觉/听觉优先），点到即止；以动作、对话推进为主，心理简洁带戏谑，不冗长不端架子
6. 结尾给出 2-3 个选项，每个选项：text（行动描述）+ type（major=重大/minor=轻）+ tension（历史干预度 0-100，顺应史实 0-30，局部干预 31-70，硬干预 71-100）+ effect（对玩家可见的后果说明）
7. 输出严格 JSON（单行，不要 markdown 代码围栏，不要换行，不要 ```json，直接输出 JSON 对象），格式：
{{"narrative": "...", "options": [{{"text": "...", "type": "major|minor", "tension": 25, "effect": "..."}}]}}
8. 严禁全知旁白宣告世界侧的无觉察（如'没人觉得不对''无人察觉'）；世界差异只经玩家内心/观察呈现
9. 选项 text/effect 严禁 meta 词与现代词出口给 NPC（如"穿越者""现代""剧本"）；玩家向 NPC 说出异常认知时，NPC 以世界逻辑自然接住或当他疯话
10. 若发生时空跳跃（跨年/大段路程），叙事须显式交代（如'数月后''几天路程'），不得无标记硬切""".strip()


def _load_persona_layer(names: list[str], distance_map: dict) -> str:
    """按距离分层组装人设"""
    lines = []
    for name in names:
        if name not in KNOWN_NAMES:
            continue
        dist = distance_map.get(name, "远观")
        if dist == "核心":
            p = PERSONA_FULL.get(name) or PERSONA_LIGHT.get(name, "")
        else:
            p = PERSONA_LIGHT.get(name, "")
        if p:
            lines.append(p)
    return "\n".join(lines) if lines else "（本场景无已知角色在场）"


def _build_context_panel(state: GameState, plan: ScenePlan, memory_pack: list = None) -> str:
    """构建完整状态面板（注入 LLM 思维链），覆盖规范 §1-§4 全部维度。

    LLM 能看到：时空/玩家/NPC内心/关系/记忆/世界动态/质量检查单。
    """
    era = state.get("era", {})
    player = state.get("player", {})
    relations = state.get("relations", {})
    trust = state.get("trust", {})
    mem = state.get("memory", {})
    flags = state.get("flags", [])
    foreshadowing = state.get("foreshadowing", [])
    rumors = state.get("world_rumors", [])
    knowledge = state.get("knowledge", {})
    tension = state.get("tension", 0)
    turn = state.get("turn", 0)

    stm = mem.get("stm", [])
    ltm = mem.get("ltm", [])
    pins = mem.get("pins", [])

    lines = []
    lines.append("=" * 50)
    lines.append("【思维链 · 状态面板】")

    # ── ⏳ 时空环境 ──
    lines.append("")
    lines.append("⏳ 时空环境")
    lines.append(f"  年份：{era.get('year', '?')}年 · {era.get('season', '?')}")
    lines.append(f"  篇章：{era.get('chapter', '?')}")
    lines.append(f"  位置：{era.get('location', plan.location)}")
    lines.append(f"  当前场景：{plan.chapter_label} · {plan.title}")
    lines.append(f"  场景设定：{plan.setting}")
    lines.append(f"  氛围基调：{plan.atmo}")
    if plan.world_normal:
        lines.append(f"  世界侧正常演出：{plan.world_normal}")

    # ── 🧍 玩家状态 ──
    lines.append("")
    lines.append("🧍 玩家状态")
    lines.append(f"  身份：{player.get('identity', '无名')}")
    lines.append(f"  性格：{player.get('personality', '沉稳')}  ← 人格铁律锁定")
    lines.append(f"  目标：{player.get('goal', '在乱世中活下去')}")
    lines.append(f"  声望：{player.get('reputation', 0)}/100")
    lines.append(f"  位置：{player.get('location', '?')}")
    inner = player.get('inner_voice', '')
    if inner:
        lines.append(f"  内心：「{inner}」")
    notes = player.get("notes", [])
    if notes:
        lines.append(f"  差异笔记：{'、'.join(notes)}")
    pov_list = plan.player_pov or []
    if pov_list:
        lines.append(f"  玩家视角差异：{'；'.join(pov_list)}")

    # ── 🧠 信息迷雾知识边界（spec §六：public 可注入 / player 仅玩家可引用）──
    knowledge = state.get("knowledge", {})
    pub = knowledge.get("public", [])
    ply = knowledge.get("player", [])
    if pub or ply:
        lines.append("")
        lines.append("🧠 知识边界（信息迷雾）")
        if pub:
            lines.append(f"  玩家已知（可正常引用）：{'；'.join(pub[-5:])}")
        if ply:
            lines.append(f"  穿越直觉（仅玩家内心可引用，NPC 不当真）：{'；'.join(ply[-3:])}")
        lines.append("  ⚠️ 世界真实（hidden）绝不泄漏：NPC 只能说自己知道的，旁白不得揭示未发生之事")

    # ── 👥 在场角色 ──
    lines.append("")
    lines.append("👥 在场角色")
    names_in_scene = set()
    for line_data in plan.locked_lines:
        sp = line_data.get("speaker", "")
        if sp and sp != "玩家":
            names_in_scene.add(sp)
    # 从 distance_map 补充
    for name in plan.distance_map:
        names_in_scene.add(name)
    # 从 relations 补充（可能在附近）
    for name in relations:
        if relations.get(name, 50) > 40:
            names_in_scene.add(name)

    if not names_in_scene:
        lines.append("  （本场景无已知角色在场）")
    else:
        for name in sorted(names_in_scene):
            if name not in KNOWN_NAMES:
                continue
            dist = plan.distance_map.get(name, "远观")
            rel = relations.get(name, 50)
            tr = trust.get(name, 50)
            persona = PERSONA_FULL.get(name) or PERSONA_LIGHT.get(name, "")
            # 提取核心性格（冒号后第一句）
            trait = persona.split("。")[0].split("：")[-1] if persona else "未知"
            lines.append(f"  {name}｜距离{ dist }｜好感{rel}/100｜信任{tr}/100")
            lines.append(f"    └ {trait}")

    # ── 📚 记忆回廊（优先用检索包 memory_pack：PIN 全部 + 检索 top-5 LTM + 当前 STM）──
    # memory_pack 为空时回退裸 state.memory（最近 5 条 LTM）
    mp = memory_pack or []
    mp_ids = {m.get("id"): m for m in mp if m.get("id")}
    # 检索包里的 LTM 条目（在 mp 且不在 stm 里）；stm 全量；pin 按 id 查
    stm_ids = {m.get("id") for m in stm}
    mp_ltm = [m for m in mp if m.get("id") and m["id"] not in stm_ids]
    # 计算 LTM 面板条目：优先检索包相关 LTM，否则最近 5 条
    panel_ltm = mp_ltm if mp_ltm else ltm[-5:]

    lines.append("")
    lines.append(f"📚 记忆回廊  STM[{len(stm)}/6]｜LTM[{len(ltm)}]｜PIN{len(pins)}条")
    # PIN
    if pins:
        all_items = {m["id"]: m for m in stm + ltm}
        if mp:
            all_items.update(mp_ids)  # 检索包优先
        lines.append("  【📌 PIN】")
        for pid in pins:
            item = all_items.get(pid)
            if item:
                sc = item.get("scene", "-")
                lines.append(f"    [{sc}] {item['text'][:80]}")
    # LTM（检索相关 top-5；无检索结果时回退最近 5 条）
    if panel_ltm:
        lines.append("  【📚 LTM】")
        for m in panel_ltm[:5]:
            sc = m.get("scene", "-")
            lines.append(f"    [{sc}] {m['text'][:120]}")
    # STM
    if stm:
        lines.append("  【📝 STM】")
        for m in stm:
            sc = m.get("scene", "-")
            tm = m.get("time", "-")
            lines.append(f"    {tm}｜{sc}｜{m['text'][:80]}")
    else:
        lines.append("  【📝 STM】（空）")

    # ── 🌐 世界动态 ──
    lines.append("")
    lines.append("🌐 世界动态")
    if rumors:
        for r in rumors[-5:]:
            lines.append(f"  · {r}")
    else:
        lines.append("  （暂无流言）")
    facts = era.get("world_facts", [])
    if facts:
        for f in facts[-3:]:
            lines.append(f"  📋 {f}")

    # ── 🔗 关系网络 ──
    if relations:
        lines.append("")
        lines.append("🔗 关系网络")
        # 核心关系 (好感 ≥ 30)
        core = {k: v for k, v in relations.items() if v >= 30}
        if core:
            lines.append("  核心：")
            for name, val in sorted(core.items(), key=lambda x: -x[1]):
                tr_val = trust.get(name, 50)
                lines.append(f"    {name} 好感{val} 信任{tr_val}")
        # 一般关系 (0 < 好感 < 30)
        general = {k: v for k, v in relations.items() if 0 < v < 30}
        if general:
            lines.append("  一般：")
            for name, val in sorted(general.items(), key=lambda x: -x[1]):
                lines.append(f"    {name} 好感{val}")

    # ── 伏笔 ──
    if foreshadowing:
        lines.append("")
        lines.append("🎯 未解伏笔/承诺")
        for fs in foreshadowing[-5:]:
            lines.append(f"  · {fs}")

    # ── 天意修正 ──
    corrected = state.get("corrected", [])
    if corrected:
        lines.append("")
        lines.append(f"⚠️ 天意修正 x{len(corrected)}（最近：{corrected[-1] if corrected else '无'}）")
        lines.append(f"  当前 tension：{tension}/100")

    # ── 锁定台词 ──
    locked = plan.locked_lines
    if locked:
        lines.append("")
        lines.append("🔒 锁定台词（必须逐字出现）")
        for l in locked:
            lines.append(f"  [{l.get('speaker', '?')}] {l.get('text', '')}")

    # ── 📋 质量检查单 ──
    lines.append("")
    lines.append("📋 质量检查单（输出前逐项确认）")
    lines.append("  □ P0 时空连续，无跳跃 | □ P1 地理/史实正确 | □ P2 回应玩家意图，追踪伏笔")
    lines.append("  □ P3 角色不OOC | □ P4 玩家不神化、关系不跳跃 | □ P5 行为有后果")
    lines.append("  □ P6 五感覆盖（光/声/味/温/触） | □ P7 字数≥600、描写均衡、情感链条完整")
    lines.append("  □ 信息迷雾无泄漏（NPC只说自己知道的事）")

    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)


def build_messages(state: GameState, plan: ScenePlan, memory_pack: list = None) -> list[dict]:
    """组装 LLM messages：system(世界底色) + 状态面板 + user(场景指令) + 历史"""
    # ── 完整状态面板（LLM 思维链）──
    context_panel = _build_context_panel(state, plan, memory_pack)

    # 人设分层
    names = [l["speaker"] for l in plan.locked_lines if l.get("speaker")]
    personas = _load_persona_layer(names, plan.distance_map)

    locked = "\n".join(
        f"[{l['speaker']}] {l['text']}" for l in plan.locked_lines
    ) or "（无）"
    pov = "\n".join(f"· {p}" for p in plan.player_pov) or "（无）"

    instruction = WRITER_INSTRUCTION.format(
        chapter_label=plan.chapter_label,
        title=plan.title,
        setting=plan.setting,
        world_normal=plan.world_normal,
        player_pov=pov,
        locked_lines=locked,
        personas=personas,
    )

    # 场景手调选项池注入（registry options：含 tension/effect，LLM 可选用或改写）
    if plan.options:
        pool = "\n".join(
            f"- {o.get('text', '')}（type={o.get('type', 'minor')} tension={o.get('tension', 0)}｜{o.get('effect', '')}）"
            for o in plan.options[:3]
        )
        instruction += "\n\n【可选骨架选项（可原样采用或在此基础上改写，至少保留 2-3 个）】\n" + pool

    # 重写失败原因注入
    retry = getattr(plan, "meta_retry", None)
    if retry:
        instruction += "\n\n【上次校验失败原因（必须针对性修复）】\n" + "\n".join(f"- {r}" for r in retry)

    messages = [{"role": "system", "content": WORLD_BASE}]
    # 状态面板作为第二个 system message
    messages.append({"role": "system", "content": context_panel})
    # 历史（最近 6 轮）
    for h in state.get("history", [])[-6:]:
        if h.get("user"):
            messages.append({"role": "user", "content": h["user"]})
        if h.get("assistant"):
            messages.append({"role": "assistant", "content": h["assistant"][:600]})
    messages.append({"role": "user", "content": instruction})
    return messages


def parse_output(text: str) -> dict:
    """解析 LLM 输出 → NarrativeOutput 雏形（容错 JSON）"""
    text = text.strip()
    # 尝试直接 JSON（LLM 可能输出数组/裸值 → 一律要求 dict）
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "narrative" in data:
            return data
    except json.JSONDecodeError:
        pass
    # 尝试提取 {...} 块
    import re
    m = re.search(r'\{.*\}', text, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict) and "narrative" in data:
                return data
        except json.JSONDecodeError:
            pass
    # 兜底：文本为叙事，选项为空
    return {"narrative": text, "options": []}


async def narrate(state: GameState, plan: ScenePlan, memory_pack: list = None, on_chunk=None) -> dict:
    """主入口：生成 NarrativeOutput（含后处理链）

    on_chunk: 可选回调（text: str）→ 用于 SSE 流式透出
    """
    from services.llm import stream_chat
    from config import PARAMS_PLAY, STOP_SEQUENCES
    from services.deslop import deslop

    messages = build_messages(state, plan, memory_pack)
    # 收集流式输出（Phase 4 经 on_chunk 透出 SSE）
    draft = ""
    async for chunk in stream_chat(
        messages, max_tokens=2048, **PARAMS_PLAY, stop=STOP_SEQUENCES
    ):
        draft += chunk
        if on_chunk:
            on_chunk(chunk)

    # LLM 全挂检测：错误占位字符串不得当叙事正文（转异常走路由 err 分支）
    if "[错误]" in draft and "LLM" in draft:
        raise RuntimeError("LLM 服务不可用")

    # 后处理链（services.validator 面向旧脚本格式，对散文近空操作且重复 deslop，已移除）
    draft = deslop(draft)
    data = parse_output(draft)
    data["narrative"] = data.get("narrative", draft)
    options = data.get("options", [])
    # 容错：LLM 把 options 生成为对象/裸值 → 落回空列表
    if not isinstance(options, list):
        options = []
    # 只保留 dict 项，避免后续 opt.get 崩溃
    options = [o for o in options if isinstance(o, dict)]
    # 选项硬上限 3、类型/数值规范
    for opt in options[:3]:
        opt["type"] = "major" if opt.get("type") == "major" else "minor"
        try:
            opt["tension"] = max(0, min(100, int(opt.get("tension", 0))))
        except (TypeError, ValueError):
            opt["tension"] = 0
    data["options"] = options[:3]

    # 后处理：从叙事文本提取 state_updates（轻量正则，不额外调 LLM）
    extracted = _extract_state_updates(data["narrative"], data["options"], plan)

    return {
        "narrative": data["narrative"],
        "options": data["options"],
        "state_updates": extracted,
        "validated": True,
        "phase_report": {},
        "retry_reasons": [],
    }


def _extract_state_updates(narrative: str, options: list, plan: ScenePlan) -> dict:
    """从叙事文本提取状态更新（纯规则，不污染主 prompt，不额外调 LLM）"""
    result: dict = {"memory_add": [], "relations_delta": {}, "trust_delta": {},
                    "foreshadowing_add": [], "rumors_add": [], "flags_add": []}

    # 1. 记忆条目：只取 1 条最重要的客观事实摘要（叙事前 80 字精炼）
    # 去除第一人称代词、内心独白标记，保留事件骨架
    first_sentence = narrative[:120].strip()
    # 找第一个句号/换行作为自然断点
    for sep in ("。", "！", "？", "\n"):
        idx = first_sentence.find(sep)
        if idx > 20:
            first_sentence = first_sentence[:idx+1]
            break
    result["memory_add"] = [first_sentence[:80]]

    # 2. 关系变化只作用于"实际互动角色"（锁定台词说话人 / distance_map 核心+互动），
    # 避免叙事泛泛提到全体已知角色造成关系噪声（原实现会对所有 KNOWN_NAMES 套同一 delta）
    interact_names = set()
    for line in plan.locked_lines:
        sp = line.get("speaker", "")
        if sp and sp in KNOWN_NAMES:
            interact_names.add(sp)
    for name, dist in (plan.distance_map or {}).items():
        if dist in ("核心", "互动"):
            interact_names.add(name)

    # 3. 简单上下文情感检测（只对互动角色）
    if interact_names:
        POS = {"帮", "救", "谢", "好", "友", "敬", "信", "护", "助", "善", "恩", "忠", "义"}
        NEG = {"敌", "杀", "恨", "贼", "疑", "怒", "逃", "谎", "骗", "叛", "奸", "恶"}
        pos_count = sum(1 for w in POS if w in narrative)
        neg_count = sum(1 for w in NEG if w in narrative)

        for name in interact_names:
            if name not in narrative:
                continue  # 没提到就不动关系
            # 好感变化：基于叙事基调 ±8 以内
            rel_delta = min(8, max(-8, (pos_count - neg_count) * 2))
            if rel_delta != 0:
                result["relations_delta"][name] = rel_delta
            # 信任变化：通常微正（见面即建立基础信任）
            trust_delta = max(-3, min(4, rel_delta // 2 + 1))
            if trust_delta != 0:
                result["trust_delta"][name] = trust_delta

    # 4. 伏笔检测（关键词）
    FORESHADOW_KW = {"日后", "有朝一日", "欠你", "承诺", "约定", "改日", "时机成熟",
                     "伏笔已埋", "必有后报", "不会忘记", "记住你了"}
    for kw in FORESHADOW_KW:
        if kw in narrative:
            idx = narrative.find(kw)
            snippet = narrative[max(0, idx - 5): idx + len(kw) + 15].strip()
            if len(snippet) > 8:
                result["foreshadowing_add"].append(snippet)
                break  # 最多一条

    # 5. 流言/军报检测（关键词）
    RUMOR_KW = {"听说", "据说", "传闻", "传言", "军报", "探马来报", "消息", "密报"}
    for kw in RUMOR_KW:
        if kw in narrative:
            idx = narrative.find(kw)
            snippet = narrative[idx: idx + 30].strip()
            if len(snippet) > 6:
                result["rumors_add"].append(snippet)
                break  # 最多一条

    # 6. flags 检测（暗线/见证者/知情者——供 director aftermath.flow 岔路与前端徽章）
    # 场景声明在 flags_on_enter 的全名 flag（如 见证者_官道之辩/见证者_刺董败露）优先产出，
    # 保证与 flags_on_enter 字符串一致（director 岔路用精确匹配）。
    # 见证者/知情者：仅当场景 flags_on_enter 声明同前缀全名 flag 才产出（避免裸前缀噪声，
    # 如"跟着"误触发暗线_流亡）；暗线_*：无场景锚定，保留裸前缀回退。
    FLAG_KW = {
        "暗线_流亡": {"流亡", "同行", "一路东逃"},
        "暗线_黄金": {"混入", "黄金军内部", "信物"},
        "暗线_许家": {"许家", "推荐信", "厚报", "救下"},
        "见证者": {"目睹", "亲眼看见", "见证"},
        "知情者": {"知道真相", "识破", "察觉"},
    }
    scene_flags = [f for f in (plan.flags_on_enter or []) if isinstance(f, str)]
    for prefix, kws in FLAG_KW.items():
        if any(kw in narrative for kw in kws):
            matched = next((f for f in scene_flags if f.startswith(prefix)), None)
            flag = matched if matched else (prefix if prefix.startswith("暗线_") else None)
            if flag and flag not in result["flags_add"]:
                result["flags_add"].append(flag)

    return result
