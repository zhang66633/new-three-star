"""
确定性验收层（Validator）—— Phase 1
====================================
叙事管线的第一道"硬约束"：在 LLM 生成之后、流式输出之前，用纯代码做
确定性校验与修复。不依赖 LLM 自觉，保证以下不变量：

- 关键道具名不可被 AI 篡改（断肠刀 → 七星宝刀）
- 选项数量恒 ≤ 3（AI 生成 9 个也只留前 3 个）
- 角色名损坏修复（[曹操作] → [曹操]）
- 分行标记合并（[曹操]\\n台词 → [曹操] 台词）

Phase 2 将在此基础上引入 Director/StoryState，把道具锁定从"事后修复"
升级为"事前锁定"（Writer 根本拿不到错误道具名）。
"""
import re

from .deslop import deslop

# ---------------------------------------------------------------------------
# 角色名修复（从 narrative.py 迁入）
# ---------------------------------------------------------------------------

# 已知角色名（含常见别称），用于纠正AI写坏的名字（如"曹操作"→"曹操"）
_KNOWN_NAMES = [
    "曹操", "刘备", "关羽", "张飞", "诸葛亮", "司马懿", "孙权", "周瑜",
    "吕布", "董卓", "袁绍", "袁术", "赵云", "陆逊", "吕蒙", "鲁肃",
    "王允", "貂蝉", "陈宫", "华佗", "献帝", "刘协", "孙策", "大乔", "小乔",
    "黄盖", "甘宁", "太史慈", "张辽", "徐晃", "夏侯惇", "夏侯渊", "许褚",
    "典韦", "郭嘉", "荀彧", "贾诩", "庞统", "法正", "马谡", "姜维", "魏延",
    "黄忠", "马超", "司马昭", "司马师", "司马炎", "曹丕", "曹植", "曹叡",
    "刘禅", "阿斗", "众人", "士兵", "侍卫", "家丁", "仆役",
]
# 非角色名的方括号标记（不参与名字纠错）
_MARKER_NAMES = {"SYS", "ERR", "MUSIC", "OPT", "角色名"}


def _fix_character_names(text: str) -> str:
    """确定性纠正AI写坏的角色名（如"[曹操作]"→"[曹操]"）。
    保守策略：方括号内若不是已知名字，但包含某个已知名字且多出的字≤2个，
    才替换为该已知名字；其余（含[众人]等合法称呼）一律不动。
    """
    def repl(m):
        name = m.group(1)
        if name in _MARKER_NAMES or name in _KNOWN_NAMES:
            return m.group(0)
        for known in _KNOWN_NAMES:
            if known in name and 0 < len(name) - len(known) <= 2:
                return f"[{known}]"
        return m.group(0)
    return re.sub(r"\[([^\[\]\n]{1,8})\]", repl, text)


def _is_speaker_name(name: str) -> bool:
    """角色名判定：1-8字、不含标点/空白（与前端 isSpeakerName 一致）。"""
    return 1 <= len(name) <= 8 and not re.search(r"[。，！？、；：\s·…—]", name)


def _merge_split_dialogue(text: str) -> str:
    """修复AI把标记单独成行、内容换到下一行的格式，合并为同行。
    - [角色名]\\n台词 → [角色名] 台词
    - [OPT]/[SYS]/[ERR]\\n内容 → [OPT] 内容 等（[MUSIC]独立标记，不合并）
    只合并下一行不是标记行的情况。
    """
    mergeable_markers = {"OPT", "SYS", "ERR"}
    lines = text.split("\n")
    merged = []
    i, n = 0, len(lines)
    while i < n:
        stripped = lines[i].strip()
        m = re.match(r"^\[([^\[\]\n]+)\]\s*$", stripped)
        if m and i + 1 < n:
            name = m.group(1)
            nxt = lines[i + 1].strip()
            is_dialogue = _is_speaker_name(name) and name not in _MARKER_NAMES
            is_marker = name in mergeable_markers
            if (is_dialogue or is_marker) and nxt and not nxt.startswith("["):
                merged.append(f"[{name}] {nxt}")
                i += 2
                continue
        merged.append(lines[i])
        i += 1
    return "\n".join(merged)


# ---------------------------------------------------------------------------
# 选项数量控制
# ---------------------------------------------------------------------------

def cap_options(text: str, max_options: int = 3) -> str:
    """选项数量硬约束：超过 max_options 个 [OPT] 行时只保留前 N 个。
    AI 生成 9 个选项也只留前 3 个——数量是确定性保证，不靠 prompt 自觉。
    """
    lines = text.split("\n")
    kept = 0
    out = []
    for ln in lines:
        if ln.strip().startswith("[OPT]"):
            kept += 1
            if kept > max_options:
                continue  # 丢弃超出上限的选项
        out.append(ln)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 关键道具名强制
# ---------------------------------------------------------------------------

# 各节点的关键道具正名 + 已知的AI编造错名（Phase 1 硬编码；
# Phase 2 迁入 knowledge/nodes.py 的"关键道具"字段，由 Director 事前锁定）
CANONICAL_ITEMS = {
    "曹操献刀": {
        "七星宝刀": ["断肠", "断肠刀"],
    },
    "桃园结义": {
        "青龙偃月刀": ["青龙刀"],
        "丈八蛇矛": ["丈八长矛", "丈八矛"],
        "双股剑": ["双剑"],
    },
}


def enforce_item_names(text: str, node: str) -> str:
    """关键道具名硬约束：
    1. 已知错名（别名表）直接替换回正名（断肠/断肠刀 → 七星宝刀）。
    2. 保守的命名模式检测：形如"此刀名曰'X'"/"宝刀名为'X'"，若 X 不是正名，
       替换为正名——兜住别名表没覆盖的新编造名。
    """
    items = CANONICAL_ITEMS.get(node, {})
    for canonical, aliases in items.items():
        # 1. 别名表替换（长别名优先，避免"断肠刀"→"七星宝刀刀"叠字）
        for alias in sorted(aliases, key=len, reverse=True):
            text = text.replace(alias, canonical)
        # 2. 命名模式检测（仅限"刀/剑/宝"被命名的场景，避免误伤；含弯引号）
        pattern = r"([刀宝剑]\s*名(?:曰|叫|为)\s*['\"『「‘’]?)([^'\"』」‘’，。！？\s]{1,8})(['\"』」‘’]?)"

        def fix_naming(m, canonical=canonical):
            if m.group(2) != canonical:
                return m.group(1) + canonical + m.group(3)
            return m.group(0)
        text = re.sub(pattern, fix_naming, text)
    return text


# ---------------------------------------------------------------------------
# 名和字混用（新三称呼特色）
# ---------------------------------------------------------------------------

# 名 → 字 对照（新三风格：名和字毫无规律混用）
_NAME_TO_COURTESY = {
    "曹操": "孟德", "刘备": "玄德", "关羽": "云长", "张飞": "翼德",
    "诸葛亮": "孔明", "司马懿": "仲达", "吕布": "奉先", "周瑜": "公瑾",
}


def ensure_name_mixing(text: str) -> str:
    """新三称呼特色是名和字毫无规律地混用。AI 有两个对称的回归倾向：
    对抗场景只用名（太统一）、客气场景只用字（太文明，"又称字了"）。
    只检查【对话行】里对主要角色的称呼（说话人≠该角色，避免改自称）：
    - 对话里只称字、从不称名 → 把一处字换成名（去掉客气味）
    - 对话里只称名、从不称字 → 把一处名换成字（制造新三式混乱）
    旁白不动；每个角色最多改一处。"""
    lines = text.split("\n")
    for name, courtesy in _NAME_TO_COURTESY.items():
        has_name = has_courtesy = False
        for line in lines:
            m = re.match(r"^\[([^\]]+)\]\s*(.*)$", line)
            if m and m.group(1) != name:  # 说话人不是该角色本人
                if name in m.group(2):
                    has_name = True
                if courtesy in m.group(2):
                    has_courtesy = True
        if not (has_name or has_courtesy):
            continue  # 对话里没提到该角色
        if has_name and has_courtesy:
            continue  # 已经混用了，不动
        # 单向 → 换一处制造混乱（只称字→换名为字；只称名→换字为名）
        src, dst = (courtesy, name) if has_courtesy else (name, courtesy)
        for i, line in enumerate(lines):
            m = re.match(r"^(\[([^\]]+)\]\s*)(.*)$", line)
            if m and m.group(2) != name and src in m.group(3):
                lines[i] = m.group(1) + m.group(3).replace(src, dst, 1)
                break
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 总入口
# ---------------------------------------------------------------------------

def validate(text: str, node: str = "") -> str:
    """确定性验收修复总入口。修复顺序：
    道具名 → 选项数量 → 角色名 → 名字混用 → 去AI味 → 分行标记合并。
    全部为确定性代码，不引入 LLM 调用。
    """
    text = enforce_item_names(text, node)
    text = cap_options(text, 3)
    text = _fix_character_names(text)
    text = ensure_name_mixing(text)
    text = deslop(text)
    text = _merge_split_dialogue(text)
    return text
