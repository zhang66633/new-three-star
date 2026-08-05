"""
槽点注入器（Absurdity Injector）——v4.0
=========================================
槽点不是"游戏bug"——是AI在生成过程中会自然出现的缺陷。
不要刻意制造它们——但当它们出现时，不要修正。
"""
import random

# --- 称呼混乱（AI上下文窗口有限，忘了角色该怎么称呼对方）---
NAME_MIX_POOL = [
    {
        "id": "name_mix_basic",
        "type": "称呼混乱",
        "difficulty": "easy",
        "instruction": (
            "让{primary_speaker}在本段对话中，对{target}的称呼在'{courtesy}'和'{name}'"
            "之间切换至少两次。{primary_speaker}本人毫无察觉，{target}也毫无反应。"
            "（AI的上下文窗口不足，记不住该用哪个称呼。）"
        ),
    },
    {
        "id": "name_mix_same_sentence",
        "type": "称呼混乱",
        "difficulty": "medium",
        "instruction": (
            "让{primary_speaker}在同一句话里，对{target}先用'{courtesy}'称呼，"
            "说到一半改口叫'{name}'（或反过来），自己完全没察觉改了口。"
            "（AI在句子生成到一半时检索了另一个称呼。）"
        ),
    },
    {
        "id": "name_mix_reverse",
        "type": "称呼混乱",
        "difficulty": "medium",
        "instruction": (
            "让{primary_speaker}对{target}用反了称呼——在应该客气的时候叫了{name}（直呼其名），"
            "在应该严厉的时候叫了{courtesy}（称呼字）。"
            "（AI的'场景得体性'检测没有启用。）"
        ),
    },
    {
        "id": "name_mix_self",
        "type": "称呼混乱",
        "difficulty": "hard",
        "instruction": (
            "让{primary_speaker}在自称时也混乱一次——平时自称'{self_name}'，"
            "本段中突然自称'{self_courtesy}'一次（如刘备平时自称'备'，某句突然自称'玄德'）。"
            "（AI的'第一人称一致性'检测被跳过了。）"
        ),
    },
]

# --- 成语瞎用（AI训练数据污染——检索了后世词语）---
IDIOM_POOL = [
    {
        "id": "idiom_wrong_saying",
        "type": "成语瞎用",
        "difficulty": "easy",
        "instruction": (
            "让{speaker}想表达'{correct_meaning}'的意思，但嘴里说出来的词是'{wrong_phrase}'。"
            "他自己坚信说得对，周围人点头称是。"
            "（AI的训练数据污染——检索到了一个不存在的成语。）"
        ),
    },
    {
        "id": "idiom_malapropism",
        "type": "成语瞎用",
        "difficulty": "medium",
        "instruction": (
            "让{speaker}想引用一句古语/俗语，但说出来的版本有微妙的关键词替换——"
            "原句是'{correct_phrase}'，他说成了'{wrong_phrase}'。"
            "{speaker}说完后，{listener}若有所思地点头'说得有理'——两人都坚信这句话古来如此。"
            "（AI的'文本真实性校验'没有启用。）"
        ),
    },
    {
        "id": "idiom_invented_proverb",
        "type": "成语瞎用",
        "difficulty": "medium",
        "instruction": (
            "让{speaker}在对话中突然说出一句'{invented_saying}'——这句话听起来像古语，"
            "但其实谁都没听过。他一本正经地引用它作为论据。"
            "（AI的'知识库真实性校验'缺失——AI编造了一句听起来像古语的句子。）"
        ),
    },
]

# --- 地理穿越（AI幻觉——对地理没有概念）---
GEO_POOL = [
    {
        "id": "geo_half_day",
        "type": "地理穿越",
        "difficulty": "easy",
        "instruction": (
            "让{speaker}在对话中随口说'{from_place}到{to_place}不过半日路程'"
            "（两地实际相隔数百甚至千里）。说得很自然，像在陈述一个众所周知的事实。"
            "在场者无人质疑。"
            "（AI的地理幻觉——在AI的概念里，这两个地方只是两个地名标签，距离不重要。）"
        ),
    },
    {
        "id": "geo_wrong_direction",
        "type": "地理穿越",
        "difficulty": "medium",
        "instruction": (
            "让{speaker}说到某个地点时，把方向完全说反了（如'{place}在东边'，实际在西边）。"
            "在场者按他说的方向点头。"
            "（AI的方向感数据表被一次错误检索覆写了。）"
        ),
    },
    {
        "id": "geo_instant_arrive",
        "type": "地理穿越",
        "difficulty": "easy",
        "instruction": (
            "旁白中主角/军队从一个地点到另一个遥远地点，中间不写行程。"
            "上句还在{from_place}，下句已在{to_place}。"
            "（AI跳过了不感兴趣的行军段落——没有做移动速度约束。）"
        ),
    },
]

# --- 时间错乱（AI没有做时间连续性检查）---
TIME_POOL = [
    {
        "id": "time_skip",
        "type": "时间错乱",
        "difficulty": "easy",
        "instruction": (
            "前后两句旁白之间，时间突然跳跃——从{time_a}直接到{time_b}。"
            "不解释中间发生了什么。旁白语气平实，仿佛时间的跳跃是完全正常的。"
            "（AI没有做时间连续性检查。）"
        ),
    },
    {
        "id": "time_season_wrong",
        "type": "时间错乱",
        "difficulty": "medium",
        "instruction": (
            "在描写季节/天气时出现矛盾——'{season_a}'和'{weather_b}'同时出现"
            "（如端午大雪、盛夏寒霜）。不解释，不抒情，就平静地写——"
            "（AI在天气和季节两个独立的提示词间没有做一致性检查。）"
        ),
    },
    {
        "id": "time_stretch",
        "type": "时间错乱",
        "difficulty": "easy",
        "instruction": (
            "写一个极短的动作，但旁白暗示过去了很长时间。"
            "如'{character}说了{short_action}'→下一句'{long_time_passed}'。"
            "（AI的时间感知模块在长上下文末尾偶尔故障。）"
        ),
    },
]

# --- 逻辑断线（AI注意力衰减，前后无关）---
LOGIC_BREAK_POOL = [
    {
        "id": "logic_sys_insert",
        "type": "逻辑断线",
        "difficulty": "hard",
        "instruction": (
            "在对话进行到一半时，{speaker}突然说出一句与当前话题完全无关的'{random_line}'。"
            "这句话应该是无意义的、日常的、微小的——像AI在测试文本生成时输出的一句废话。"
            "插入方式：说完'{random_line}'后，{speaker}若无其事地继续之前的话题。"
            "在场者无人反应——"
            "在这句话前面插入一个[SYS]标记（如'[SYS] 注意力衰减——无关语句已跳过'）。"
            "（AI在长对话中注意力衰减，检索到了一段无关的文本。）"
        ),
    },
    {
        "id": "logic_answer_wrong_question",
        "type": "逻辑断线",
        "difficulty": "medium",
        "instruction": (
            "让{character_a}问{character_b}一个问题，{character_b}的回答与问题有微妙的"
            "错位——回答的内容大致相关，但回答的角度/前提与问题不对。"
            "像两个人在用有0.5秒延迟的语音通话。"
            "（AI在长对话中丢失了前面问题的精确上下文，回答了一个相似但不相同的问题。）"
        ),
    },
    {
        "id": "logic_sudden_emotion",
        "type": "逻辑断线",
        "difficulty": "medium",
        "instruction": (
            "让{character}的情绪在本段中出现一次极其突然的、无理由的切换——"
            "从{emotion_a}突然变成{emotion_b}，然后又切回{emotion_a}。"
            "情绪切换的原因完全不在文本中——"
            "（AI在生成中检索到了不同的角色情绪模板，中途切换了一次。）"
        ),
    },
]


# 预设的错误配对（从AI常见错误中整理）
WRONG_IDIOMS = [
    {"correct": "破釜沉舟", "wrong": "破罐破摔", "meaning": "决一死战"},
    {"correct": "三顾茅庐", "wrong": "三顾茅厕", "meaning": "诚心拜访"},
    {"correct": "卧薪尝胆", "wrong": "卧冰尝雪", "meaning": "忍辱负重"},
    {"correct": "一鸣惊人", "wrong": "一叫惊人", "meaning": "突然成名"},
    {"correct": "画蛇添足", "wrong": "画龙添角", "meaning": "多此一举"},
    {"correct": "杯弓蛇影", "wrong": "杯弓虫影", "meaning": "疑神疑鬼"},
    {"correct": "指鹿为马", "wrong": "指驴为马", "meaning": "颠倒是非"},
]

GEO_WARP_PAIRS = [
    {"from": "许昌", "to": "洛阳", "actual": "约四百里", "game": "半日"},
    {"from": "荆州", "to": "许昌", "actual": "约千里", "game": "一日"},
    {"from": "成都", "to": "洛阳", "actual": "两千里", "game": "三日"},
    {"from": "徐州", "to": "长安", "actual": "千里", "game": "一日半"},
    {"from": "建业", "to": "许昌", "actual": "千里", "game": "一日"},
    {"from": "当阳", "to": "洛阳", "actual": "千里", "game": "不到一日"},
]

TIME_SKIP_PAIRS = [
    {"time_a": "正午", "time_b": "夜深"},
    {"time_a": "清晨", "time_b": "黄昏"},
    {"time_a": "午后", "time_b": "黎明"},
    {"time_a": "傍晚", "time_b": "正午"},
    {"time_a": "日出时分", "time_b": "月上中天"},
]

SEASON_WEATHER_PARADOX = [
    {"season": "端午", "weather": "大雪纷飞"},
    {"season": "盛夏", "weather": "寒风刺骨"},
    {"season": "隆冬", "weather": "烈日当空"},
    {"season": "初春", "weather": "落叶满地"},
    {"season": "中秋", "weather": "雷雨交加"},
]


def pick_absurdity(
    beat_desc: str = "",
    node: str = "",
    difficulty: str = "easy",
    count: int = 1,
) -> list[dict]:
    """为当前节拍选定AI缺陷注入指令。"""

    dialogue_keywords = ["对话", "说", "问", "答", "笑", "怒", "骂", "泣", "嘲", "议"]
    travel_keywords = ["赶路", "行军", "追击", "逃", "追杀", "出发", "启程"]
    climax_keywords = ["刺", "献刀", "死", "杀", "火烧", "托孤", "结义", "驾崩"]

    if any(k in beat_desc for k in climax_keywords):
        pools = [LOGIC_BREAK_POOL, IDIOM_POOL]
    elif any(k in beat_desc for k in travel_keywords):
        pools = [GEO_POOL, TIME_POOL]
    elif any(k in beat_desc for k in dialogue_keywords):
        pools = [NAME_MIX_POOL, IDIOM_POOL]
    else:
        pools = [NAME_MIX_POOL, IDIOM_POOL, GEO_POOL, TIME_POOL]

    all_candidates = []
    for pool in pools:
        for item in pool:
            if difficulty == "easy" and item["difficulty"] == "easy":
                all_candidates.append(item)
            elif difficulty == "medium":
                all_candidates.append(item)
            elif difficulty == "mixed":
                all_candidates.append(item)
            else:
                if item["difficulty"] in ("easy", "medium"):
                    all_candidates.append(item)

    if not all_candidates:
        all_candidates = NAME_MIX_POOL

    selected = []
    used_types = set()
    shuffled = random.sample(all_candidates, len(all_candidates))

    for item in shuffled:
        if item["type"] not in used_types:
            selected.append({
                "type": item["type"],
                "difficulty": item["difficulty"],
                "instruction": item["instruction"],
                "note": item.get("note", ""),
            })
            used_types.add(item["type"])
        if len(selected) >= count:
            break

    return selected


def fill_absurdity_template(instruction: str, context: dict) -> str:
    """用上下文填充槽点模板中的占位符。"""
    try:
        return instruction.format(**context)
    except KeyError as e:
        missing = str(e).strip("'")
        context.setdefault(missing, "某人")
        return instruction.format(**context)


# 主要角色的名、字、自称对照表
CHARACTER_NAMES = {
    "曹操": {"name": "曹操", "courtesy": "孟德", "self": "吾"},
    "刘备": {"name": "刘备", "courtesy": "玄德", "self": "备"},
    "关羽": {"name": "关羽", "courtesy": "云长", "self": "关某"},
    "张飞": {"name": "张飞", "courtesy": "翼德", "self": "俺"},
    "诸葛亮": {"name": "诸葛亮", "courtesy": "孔明", "self": "亮"},
    "司马懿": {"name": "司马懿", "courtesy": "仲达", "self": "老夫"},
    "周瑜": {"name": "周瑜", "courtesy": "公瑾", "self": "瑜"},
    "孙权": {"name": "孙权", "courtesy": "仲谋", "self": "权"},
    "吕布": {"name": "吕布", "courtesy": "奉先", "self": "布"},
    "董卓": {"name": "董卓", "courtesy": "仲颖", "self": "咱家"},
    "袁绍": {"name": "袁绍", "courtesy": "本初", "self": "绍"},
    "袁术": {"name": "袁术", "courtesy": "公路", "self": "朕"},
    "王允": {"name": "王允", "courtesy": "子师", "self": "老夫"},
    "赵云": {"name": "赵云", "courtesy": "子龙", "self": "云"},
    "陆逊": {"name": "陆逊", "courtesy": "伯言", "self": "逊"},
    "鲁肃": {"name": "鲁肃", "courtesy": "子敬", "self": "肃"},
    "荀彧": {"name": "荀彧", "courtesy": "文若", "self": "彧"},
    "许褚": {"name": "许褚", "courtesy": "仲康", "self": "某"},
}


def get_character_context(character_name: str) -> dict:
    """获取角色的名、字、自称。"""
    return CHARACTER_NAMES.get(character_name, {
        "name": character_name,
        "courtesy": character_name,
        "self": "某",
    })