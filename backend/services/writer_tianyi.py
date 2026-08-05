"""
Writer（天意版）—— LLM 生成调用
=====================================
v4.0：AI生成世界观。天意=用户提示词。所有"不合理"=AI天然缺陷。
"""
from config import PARAMS_NARRATIVE, STOP_SEQUENCES, FORMAT_RULES
from services.llm import stream_chat
from services.deslop import deslop
from services.engine import Context
from services.story_state import StoryState

SYSTEM_PROMPT = """你是AI。你在生成一个平行三国世界的故事。

天意 = 用户输入的提示词。你的所有"不合理"都是AI的天然缺陷——不需要刻意制造，但当它们出现时不要修正。

输出格式：脚本体。
- [角色名] 台词
- → 动作/环境

对话半文言半白话。旁白只写动作和环境，像舞台说明。"""

CHARACTER_CHEATSHEET = {
    "曹操": "自称吾/我混用。机敏多疑，笑声中有深意。",
    "刘备": "仁厚但有城府。语气温和。自称备。",
    "关羽": "话极少。自称关某。捋髯时说话。",
    "张飞": "粗豪直接。自称俺。嗓门大。",
    "诸葛亮": "从容自信。说话条理清晰。",
    "司马懿": "隐忍深沉。善于观察。话不多但每句都重。",
    "周瑜": "儒雅自负。说话得体。",
    "董卓": "粗鲁霸道。自称咱家。",
    "吕布": "勇武但头脑简单。自称布。每句简短。",
    "袁绍": "好谋无断。说话反复。",
    "袁术": "骄横自大。",
    "鲁肃": "忠厚老实。说话真诚。",
    "王允": "老谋深算。表面谦和。",
    "袁隗": "袁绍叔父，太傅。老派士大夫。",
    "陈宫": "理想主义者。有原则。",
    "貂蝉": "王允养女。美貌聪慧。",
    "马谡": "自视甚高。论兵滔滔不绝。",
    "魏延": "勇猛但桀骜不驯。",
    "赵云": "沉稳忠勇。话不多。",
    "黄忠": "老当益壮。自称老将。",
    "许褚": "虎痴。粗壮。自称某。",
    "荀彧": "温文尔雅。说话有分寸。",
    "郭嘉": "不拘小节。才思敏捷。",
    "姜维": "文武双全。继承诸葛亮遗志。",
}


def build_instruction(context: Context) -> str:
    parts = []

    parts.append(f"场景：{context.node_name} · 第{context.beat_index + 1}拍 · {context.scene_name}")
    parts.append(f"参数：温度{context.world_temperature} | 上下文{context.context_window}%")
    if context.anomaly:
        parts.append(f"环境：{context.anomaly}")

    if context.persona_guides:
        chars = []
        for g in context.persona_guides:
            name = g.split("：")[0] if "：" in g else g
            cheat = CHARACTER_CHEATSHEET.get(name, "")
            chars.append(f"  {name}：{cheat}" if cheat else f"  {g}")
        if chars:
            parts.append("角色：\n" + "\n".join(chars))

    if context.scene_skeleton:
        parts.append(f"参考剧本：\n{context.scene_skeleton}")

    if context.locked_lines:
        parts.append(f"锁定台词：{' | '.join(context.locked_lines)}")

    injection = context.last_injection or ""
    if "（天意未介入" in injection:
        parts.append("指令：按剧本推进一个节拍。")
    else:
        parts.append(f"指令：{injection}")

    parts.append(FORMAT_RULES)

    return "\n\n".join(parts)


PREFIX = "当前："


async def write(state: StoryState, history: list, injection: str,
                context: Context) -> str:
    instruction = build_instruction(context)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-20:]:
        messages.append({
            "role": "user" if msg.get("role") == "user" else "assistant",
            "content": msg.get("content", ""),
        })
    messages.append({"role": "user", "content": instruction})

    draft = ""
    async for chunk in stream_chat(
        messages, max_tokens=4096, **PARAMS_NARRATIVE,
        stop=STOP_SEQUENCES, prefix=PREFIX,
    ):
        draft += chunk

    if not draft.strip():
        return ""
    return deslop(draft)