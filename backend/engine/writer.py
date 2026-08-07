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
    "孙策", "汉献帝", "小黄门", "黄金兵", "老者", "黑影", "乡绅",
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
1. 绝不出现 meta 语言：不出现"系统/AI/世界是假的/你在游戏中"等字样
2. 绝不出现"点明不对劲"的提示：不写"没人觉得不对""后面是什么来着""世界跳过了一截"这类旁白/台词——世界完全正常地演出，玩家自己察觉差异
3. 世界漏洞只通过玩家视角呈现：玩家是穿越者，用自己的认知对比发现偏差（如知道"黄巾"却看到"黄金"）——但世界侧一切正常，NPC 永不讨论这些偏差
4. NPC 对玩家来历从不过问，正常对话自然接纳
5. 历史大势不可推翻，但修正留痕且过程可被改写
6. 玩家的关系、声望、记忆永远生效
7. 输出为叙事文本 + 2-3 个选项；选项须是"少而重大"的道德两难或行动抉择
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
1. 生成 300-600 字叙事正文（第二人称"你"），描写当前场景
2. 玩家视角差异通过玩家内心/观察自然呈现（如：你记得史书上写的是'黄巾'……），但世界侧一切正常
3. 结尾给出 2-3 个选项，每个选项：text（行动描述）+ type（major=重大/minor=轻）+ tension（历史干预度 0-100，顺应史实 0-30，局部干预 31-70，硬干预 71-100）+ effect（对玩家可见的后果说明）
4. 输出严格 JSON，格式：
{{"narrative": "...", "options": [{{"text": "...", "type": "major|minor", "tension": 25, "effect": "..."}}]}}
""".strip()


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


def build_messages(state: GameState, plan: ScenePlan) -> list[dict]:
    """组装 LLM messages：system(世界底色) + user(场景指令) + 历史"""
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

    messages = [{"role": "system", "content": WORLD_BASE}]
    # 历史（最近 8 轮）
    for h in state.get("history", [])[-8:]:
        if h.get("user"):
            messages.append({"role": "user", "content": h["user"]})
        if h.get("assistant"):
            messages.append({"role": "assistant", "content": h["assistant"][:800]})
    messages.append({"role": "user", "content": instruction})
    return messages


def parse_output(text: str) -> dict:
    """解析 LLM 输出 → NarrativeOutput 雏形（容错 JSON）"""
    text = text.strip()
    # 尝试直接 JSON
    try:
        data = json.loads(text)
        if "narrative" in data:
            return data
    except json.JSONDecodeError:
        pass
    # 尝试提取 {...} 块
    import re
    m = re.search(r'\{.*\}', text, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            if "narrative" in data:
                return data
        except json.JSONDecodeError:
            pass
    # 兜底：文本为叙事，选项为空
    return {"narrative": text, "options": []}


async def narrate(state: GameState, plan: ScenePlan) -> dict:
    """主入口：生成 NarrativeOutput（含后处理链）

    TODO(Phase 2): validate 重写循环、remember 记忆检索注入
    """
    from services.llm import stream_chat
    from config import PARAMS_PLAY, STOP_SEQUENCES
    from services.validator import validate as deterministic_fix
    from services.deslop import deslop

    messages = build_messages(state, plan)
    # 收集流式输出（Phase 4 改为经 graph 透出 chunk）
    draft = ""
    async for chunk in stream_chat(
        messages, max_tokens=2048, **PARAMS_PLAY, stop=STOP_SEQUENCES
    ):
        draft += chunk

    # 后处理链
    draft = deslop(draft)
    data = parse_output(draft)
    data["narrative"] = deterministic_fix(data.get("narrative", draft))
    options = data.get("options", [])
    # 选项硬上限 3、类型/数值规范
    for opt in options[:3]:
        opt["type"] = "major" if opt.get("type") == "major" else "minor"
        try:
            opt["tension"] = max(0, min(100, int(opt.get("tension", 0))))
        except (TypeError, ValueError):
            opt["tension"] = 0
    data["options"] = options[:3]

    return {
        "narrative": data["narrative"],
        "options": data["options"],
        "state_updates": data.get("state_updates", {}),
        "validated": True,
        "phase_report": {},
        "retry_reasons": [],
    }
