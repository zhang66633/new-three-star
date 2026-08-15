"""
槽点注入器（Absurdity Injector）
=================================
把抽象的槽点规则变成具体的、可执行的指令模板。

核心原则：不要让 AI "创造" 荒诞 —— 代码选定荒诞，AI 负责"一本正经演出"。

每条槽点包含：
- type: 槽点类别（称呼混乱/成语瞎用/地理穿越/时间错乱/逻辑断线）
- difficulty: easy（AI容易执行）/ medium（需要技巧）/ hard（需要强控制）
- instruction: 2-3句具体可执行的指令
- fallback: 如果主槽点不适合当前拍，可用的替代方案

使用方式：
    from knowledge.absurdity_injections import pick_absurdity
    absurdity = pick_absurdity(beat_desc, difficulty="easy")
    # 然后注入到 build_beat_instruction() 的【本拍槽点】段
"""

import random

# ============================================================================
# 槽点模板库
# ============================================================================

# --- 称呼混乱（名和字毫无规律混用）---
NAME_MIX_POOL = [
    {
        "id": "name_mix_basic",
        "type": "称呼混乱",
        "difficulty": "easy",
        "instruction": (
            "让{primary_speaker}在本段对话中，对{target}的称呼在'{courtesy}'和'{name}'"
            "之间混用一次。{primary_speaker}本人毫无察觉，{target}也毫无反应，"
            "像两个称呼是同一个词。全场景只做这一处，一嘴带过，绝不停留。"
        ),
        "note": "兜底槽点，仅在没有其他槽点可用时使用。关键是'切换要自然'——不是故意切换，是嘴里随机蹦出来。",
    },
    {
        "id": "name_mix_same_sentence",
        "type": "称呼混乱",
        "difficulty": "medium",
        "instruction": (
            "让{primary_speaker}在同一句话里，对{target}先用'{courtesy}'称呼，"
            "说到一半改口叫'{name}'（或反过来），自己完全没察觉改了口。"
            "例如：'{courtesy}……不，{name}，你听我说……'——但'{primary_speaker}'没意识到"
            "自己为什么突然改口，话题继续，不做停顿。"
        ),
    },
    {
        "id": "name_mix_reverse",
        "type": "称呼混乱",
        "difficulty": "medium",
        "instruction": (
            "让{primary_speaker}对{target}用反了称呼——在应该客气的时候叫了{name}（直呼其名），"
            "在应该严厉的时候叫了{courtesy}（称呼字，偏客气）。两个场合的称呼与情绪完全错位。"
            "但{target}对两种场合的反应都一样——因为NPC的名字识别模块不分语境。"
        ),
    },
    {
        "id": "name_mix_self",
        "type": "称呼混乱",
        "difficulty": "hard",
        "instruction": (
            "让{primary_speaker}在自称时也混乱一次——平时自称'{self_name}'，"
            "本段中突然自称'{self_courtesy}'一次（如刘备平时自称'备'，某句突然自称'玄德'）。"
            "他自己毫无察觉，听的人也毫无反应——NPC的自称字段偶尔被系统覆写。"
        ),
    },
]

# --- 成语瞎用（说错成语/俗语）---
IDIOM_POOL = [
    {
        "id": "idiom_wrong_saying",
        "type": "成语瞎用",
        "difficulty": "easy",
        "instruction": (
            "让{speaker}用错一个成语——他说的是'{wrong_phrase}'（说得似是而非）。"
            "他说完就照常往下说，周围人照常附和、接话。"
        ),
        "note": "关键是'{wrong_phrase}'必须是一个听起来像成语但不完全正确的短语，不要太离谱，"
                "要让人听完需要反应半秒才觉得不对劲。",
    },
    {
        "id": "idiom_malapropism",
        "type": "成语瞎用",
        "difficulty": "medium",
        "instruction": (
            "让{speaker}引用一句古语/俗语，但版本有微妙的关键词替换——"
            "他说成了'{wrong_phrase}'。"
            "{speaker}说完后，{listener}若有所思地点头：'说得有理。'"
        ),
    },
    {
        "id": "idiom_invented_proverb",
        "type": "成语瞎用",
        "difficulty": "medium",
        "instruction": (
            "让{speaker}在对话中突然说出一句'{invented_saying}'——这句话听起来像古语，"
            "但其实谁都没听过。他一本正经地引用它作为论据。"
            "在场者无人质疑——NPC的知识库里没有'这句话不存在'的校验。"
        ),
    },
]

# --- 逻辑滑点（看似合理，细想才是废话——主力槽点）---
LOGIC_SLIP_POOL = [
    {
        "id": "logic_cause_reversed",
        "type": "逻辑滑点（因果颠倒）",
        "difficulty": "easy",
        "instruction": (
            "让{speaker}把因果倒着说——把结果说成原因，把'因为A所以B'说成'因为B所以A'。"
            "听起来振振有词，细想顺序是反的。他说完，{listener}照常附和，照常接话。"
        ),
    },
    {
        "id": "logic_number_gap",
        "type": "逻辑滑点（数字对不上）",
        "difficulty": "easy",
        "instruction": (
            "让{speaker}报出一个和语境明显对不上的数字——兵力、路程、时间、年月，"
            "差了一个数量级。他说得很自然，像陈述常识。在场者照常接受，没人算这笔账。"
        ),
    },
    {
        "id": "logic_wrong_premise",
        "type": "逻辑滑点（前提有错）",
        "difficulty": "medium",
        "instruction": (
            "让{speaker}基于一个站不住的前提，推导出一个听着很合理的结论。"
            "前提的错不是夸张，是方向性错误。结论一本正经说出来，周围人照常接话。"
        ),
    },
    {
        "id": "logic_circular",
        "type": "逻辑滑点（绕圈论证）",
        "difficulty": "medium",
        "instruction": (
            "让{speaker}说一大段论证，语气笃定，但绕了一圈，结论还是开头那句——"
            "用结论证明了结论，信息量约等于零，却讲得像发现了天机。"
        ),
    },
    {
        "id": "logic_answer_shift",
        "type": "逻辑滑点（答非所问但貌似合理）",
        "difficulty": "medium",
        "instruction": (
            "让{character_a}问{character_b}一个问题，{character_b}的回答方向性偏移——"
            "内容相关、语气笃定，但细看回答的其实不是那个问题。"
            "{character_a}不追问，对话照常往下走。"
        ),
    },
    {
        "id": "logic_sudden_emotion",
        "type": "逻辑滑点（情绪错位）",
        "difficulty": "medium",
        "instruction": (
            "让{character}的情绪在本段中突然切换一次——该悲时平静，该怒时含笑，"
            "切换的原因完全不在文本里。他照常把话说完，在场者照常继续刚才的谈话。"
        ),
    },
]

# --- 地理穿越（距离随意）---
GEO_POOL = [
    {
        "id": "geo_half_day",
        "type": "地理穿越",
        "difficulty": "easy",
        "instruction": (
            "让{speaker}在对话中随口说'{from_place}到{to_place}不过半日路程'"
            "（两地实际相隔数百甚至千里）。说得很自然，像在陈述一个众所周知的事实。"
            "在场者无人质疑——在游戏地图上，这两地确实只有半日。"
        ),
    },
    {
        "id": "geo_wrong_direction",
        "type": "地理穿越",
        "difficulty": "medium",
        "instruction": (
            "让{speaker}说到某个地点时，把方向完全说反了（如'{place}在东边'，"
            "实际在西边）。在场者按他说的方向点头——NPC的地图数据表被天意改过。"
        ),
    },
    {
        "id": "geo_instant_arrive",
        "type": "地理穿越",
        "difficulty": "easy",
        "instruction": (
            "旁白中主角/军队从一个地点到另一个遥远地点，中间不写行程。"
            "上句还在{from_place}，下句已在{to_place}。像游戏里的快速旅行加载画面被跳过了。"
        ),
    },
]

# --- 时间错乱（时间跳跃/不一致）---
TIME_POOL = [
    {
        "id": "time_skip",
        "type": "时间错乱",
        "difficulty": "easy",
        "instruction": (
            "前后两句旁白之间，时间突然跳跃——从{time_a}直接到{time_b}。"
            "不解释中间发生了什么。旁白语气平实，仿佛时间的跳跃是完全正常的。"
        ),
    },
    {
        "id": "time_season_wrong",
        "type": "时间错乱",
        "difficulty": "medium",
        "instruction": (
            "在描写季节/天气时出现矛盾——'{season_a}'和'{weather_b}'同时出现"
            "（如端午大雪、盛夏寒霜）。不解释，不抒情，就平静地写——"
            "像世界的时间参数被搅乱了。"
        ),
    },
    {
        "id": "time_stretch",
        "type": "时间错乱",
        "difficulty": "easy",
        "instruction": (
            "写一个极短的动作，但旁白暗示过去了很长时间。"
            "如'{character}说了{short_action}'→下一句'{long_time_passed}'。"
            "动作和流逝的时间之间不成比例——NPC的时间感知模块偶尔故障。"
        ),
    },
]

# 旧 LOGIC_BREAK_POOL（[SYS]随机废话/逻辑断线）已并入 LOGIC_SLIP_POOL，删除。


# ============================================================================
# 预设的槽点组合（成语瞎用 + 地名 的具体配对）
# ============================================================================

# 预设的"错误成语"配对表（从素材库中整理）
WRONG_IDIOMS = [
    {"correct": "三顾茅庐", "wrong": "三顾茅厕", "meaning": "诚心拜访"},
    {"correct": "卧薪尝胆", "wrong": "卧冰尝雪", "meaning": "忍辱负重"},
    {"correct": "一鸣惊人", "wrong": "一叫惊人", "meaning": "突然成名"},
    {"correct": "画蛇添足", "wrong": "画龙添角", "meaning": "多此一举"},
    {"correct": "杯弓蛇影", "wrong": "杯弓虫影", "meaning": "疑神疑鬼"},
    {"correct": "指鹿为马", "wrong": "指驴为马", "meaning": "颠倒是非"},
]

# 预设的地理穿越配对
GEO_WARP_PAIRS = [
    {"from": "许昌", "to": "洛阳", "actual": "约四百里", "game": "半日"},
    {"from": "荆州", "to": "许昌", "actual": "约千里", "game": "一日"},
    {"from": "成都", "to": "洛阳", "actual": "两千里", "game": "三日"},
    {"from": "徐州", "to": "长安", "actual": "千里", "game": "一日半"},
    {"from": "建业", "to": "许昌", "actual": "千里", "game": "一日"},
    {"from": "当阳", "to": "洛阳", "actual": "千里", "game": "不到一日"},
]

# 预设的时间跳跃配对
TIME_SKIP_PAIRS = [
    {"time_a": "正午", "time_b": "夜深"},
    {"time_a": "清晨", "time_b": "黄昏"},
    {"time_a": "午后", "time_b": "黎明"},
    {"time_a": "傍晚", "time_b": "正午"},
    {"time_a": "日出时分", "time_b": "月上中天"},
]

# 季节/天气矛盾配对
SEASON_WEATHER_PARADOX = [
    {"season": "端午", "weather": "大雪纷飞"},
    {"season": "盛夏", "weather": "寒风刺骨"},
    {"season": "隆冬", "weather": "烈日当空"},
    {"season": "初春", "weather": "落叶满地"},
    {"season": "中秋", "weather": "雷雨交加"},
]


# ============================================================================
# 主函数：为当前拍选定槽点
# ============================================================================

def pick_absurdity(
    beat_desc: str = "",
    node: str = "",
    difficulty: str = "easy",
    count: int = 1,
) -> list[dict]:
    """
    为当前节拍选定槽点注入指令。

    参数:
        beat_desc: 节拍描述（用于匹配合适的槽点类型）
        node: 节点名（用于避免重复）
        difficulty: 难度偏好 "easy" / "medium" / "mixed"
        count: 返回几个槽点（通常 1-2 个）

    返回:
        list[dict]: 选定的槽点指令，每条包含 type / difficulty / instruction
    """

    # 根据节拍内容判断哪种槽点更合适
    # - 行军/移动为主的拍 → 地理穿越、时间错乱
    # - 其余（对话/剧情/转折） → 逻辑滑点为主，偶尔成语
    # - 名字错位只在没有其他槽点可用时兜底

    travel_keywords = ["赶路", "行军", "追击", "逃", "追杀", "出发", "启程"]

    if any(k in beat_desc for k in travel_keywords):
        # 行军/移动拍：地理穿越 OR 时间错乱
        pools = [GEO_POOL, TIME_POOL]
    else:
        # 对话/剧情/高潮拍：逻辑滑点为主，偶尔成语
        pools = [LOGIC_SLIP_POOL, IDIOM_POOL]

    # 展平所有可用槽点
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
                # 默认：easy + medium
                if item["difficulty"] in ("easy", "medium"):
                    all_candidates.append(item)

    if not all_candidates:
        all_candidates = NAME_MIX_POOL  # 兜底

    # 随机选（不重复类型）
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
    """
    用上下文填充槽点模板中的占位符。

    context 应包含：
        - primary_speaker: 本拍主要说话人
        - target: 被称呼/被描述的对象
        - name / courtesy: 该对象的名和字
        - 其他模板中所需的占位符

    返回:
        填充后的可执行指令字符串
    """
    try:
        return instruction.format(**context)
    except KeyError as e:
        # 缺少占位符时，尽力填充
        missing = str(e).strip("'")
        # 用通用占位符替代
        context.setdefault(missing, "某人")
        return instruction.format(**context)


# ============================================================================
# 槽点上下文构造器（根据节点和节拍推断角色参数）
# ============================================================================

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
