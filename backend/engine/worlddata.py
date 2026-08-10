# -*- coding: utf-8 -*-
"""
WorldData（世界数据层 · 时间线 + 常态设定）
==========================================
加载历史事件时间线（history_timeline_*.json）+ 世界常态设定（world_normal_*.json），
提供：
  1. `phase_of(world_date)`    —— 按玩家当前日期判断所处阶段
  2. `normal_for(phase_idx)`   —— 取某阶段的常态设定（五维）
  3. `events_around(date)`     —— 按日期取事件（用于简报/场景注入）
  4. `world_context(world_date, location)` —— 综合常态+近期事件，供 writer 注入

数据源（另 AI 产出）：
  backend/knowledge/history_timeline/history_timeline_{1..4}.json
  backend/knowledge/world_normal/world_normal_{1..6}.json
"""
import json
import os

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge")

# 阶段定义：按产出文件顺序（黄金乱起 → 天下三分）
# 边界对齐时间线事件语义点（B-⑤）：
#   P1 到 189-07（黄金军+余波/前夜，无空窗）→ P2 189-08 = 董卓进京事件起
#   P2 到 192-03（董卓乱政全程）→ P3 192-04 = 董卓伏诛事件起（群雄割据真正开始）
# 边界连续（前一阶段 end 的次月 = 后一阶段 start），phase_of 无空窗。
PHASES = [
    {"idx": 1, "name": "黄金乱起", "start": "184-02", "end": "189-07"},
    # 阶段边界按剧本篇章对齐（Plan 裁决）：190 年名场面（会盟/温酒/三英）内容在 world_normal_2
    # （董卓乱政），故 P2 收在 190-12；P3 群雄割据从 191-01 起。董卓伏诛（192）场景章归 P4、日期章归 P3。
    {"idx": 2, "name": "董卓乱政", "start": "189-08", "end": "190-12"},
    {"idx": 3, "name": "群雄割据", "start": "191-01", "end": "199-12"},
    {"idx": 4, "name": "官渡定鼎", "start": "200-01", "end": "207-12"},
    {"idx": 5, "name": "赤壁三足", "start": "208-01", "end": "219-12"},
    {"idx": 6, "name": "天下三分", "start": "220-01", "end": "230-12"},
]


def _ym(date_key: str) -> tuple:
    """'184-02' → (184, 2)；容错非标准格式"""
    try:
        y, m = str(date_key).split("-")[:2]
        return int(y), int(m)
    except (ValueError, AttributeError):
        return (0, 0)


# ═════════ 地点导航（自由沙盒 · 见设计 §5.2）═════════
# 地点 → 涉及场景（对齐 registry.json 场景的 location 归属；顺序即解锁次序，也是 action_days 距离基准）
# 回访目标 = 该地点"最后访问过"的场景（记忆中的场景，LLM 圆场时间冲突）
# 顺序按地理序（距离经济 = 索引差）：颍川→长安→洛阳→汜水关→成皋→中牟→陈留→冀州
# 虎牢关并入成皋（P3_s3_three 挂成皋）；汜水关 = 温酒斩华雄主场（P3_s2_huaxiong）
LOCATIONS: dict[str, list[str]] = {
    "颍川": ["P1_s1_rain", "P1_s2_gold"],
    "长安": ["P4_s1_fengyiting", "P4_s2_lijueguosi"],
    "洛阳": ["P1_s3_leap", "P2_s1_street", "P2_s2_ci"],
    "汜水关": ["P3_s2_huaxiong"],
    "成皋": ["P2_s4_slaughter", "P3_s3_three"],
    "中牟": ["P2_s3_escape"],
    "陈留": ["P3_s1_alliance"],
    "冀州": [],
    # P5 追加（表尾，保持前 8 地相对顺序零回归；新 3 地彼此相邻）
    "许都": [],  # 曹操迎帝/煮酒论英雄 主场（196 起；P5 场景挂此）
    "徐州": [],  # 三让徐州/辕门射戟/吕布之命/袁术败亡 主场（P5 场景挂此）
    "小沛": [],  # 辕门射戟 相关（吕布暂驻）
    # 官渡批追加（表尾）：200 起官渡定鼎 + 荆州线
    "官渡": [],  # 官渡之战/袁绍败亡 主场（官渡批场景挂此）
    "荆州": [],  # 刘备投荆州/三顾茅庐 主场（官渡批场景挂此）
    # 赤壁批追加（表尾）：208 起赤壁三足
    "南郡": [],  # 长坂坡/赤壁/借荆州/周瑜之死 主场（赤壁批场景挂此）
    "赤壁": [],  # 赤壁之战/华容道 主场
    "益州": [],  # 张松献图/刘备入川/落凤坡 主场（210 起）
    "成都": [],  # 益州易主 主场
    "合肥": [],  # 合肥大战/逍遥津 主场
    "汉中": [],  # 汉中之战 主场（219）
    "麦城": [],  # 水淹七军/败走麦城 主场
}


# 传闻地点（自由沙盒 §5.2）：玩家在 X 地能听到的远方传闻 → 把目标地点点亮为"传闻"态。
# hint = 传闻文本（前端地图显示 + writer 注入让 NPC 顺口带出）；target 未解锁才点亮。
# 打听解锁：玩家「打听X」命中传闻中的地点 → 该地升级为已解锁（可赶路，director.resolve_rumor）。
LOCATION_RUMORS: dict[str, list[dict]] = {
    "颍川": [
        {"target": "洛阳", "hint": "北边传闻，洛阳最近不太平，车马都往城外逃"},
        {"target": "中牟", "hint": "商旅说东边有座中牟县城，城墙低矮，过得去"},
        {"target": "许都", "hint": "南边传闻，曹操把天子迎到许都，新都正大兴土木"},
    ],
    "洛阳": [
        {"target": "中牟", "hint": "东边传闻，中牟县城设了关卡，正盘查往来行商"},
        {"target": "成皋", "hint": "过虎牢往东，成皋关城据传屯了重兵"},
        {"target": "长安", "hint": "西边传闻，董相国要把朝廷搬到长安，火烧洛阳只差一道令"},
        {"target": "汜水关", "hint": "东出洛阳头一道关，近日西凉军陈兵关前"},
        {"target": "冀州", "hint": "北边传来袁本初在冀州招兵买马的消息"},
        {"target": "许都", "hint": "东边传来曹操奉天子迁都许县，新都气派盖过洛阳"},
    ],
    "中牟": [
        {"target": "陈留", "hint": "县里人传，陈留近来广发帖子，邀各方豪杰赴会"},
        {"target": "汜水关", "hint": "往西的虎牢关正打仗，过关要查细作"},
        {"target": "冀州", "hint": "北边传来袁绍出奔冀州的风声"},
    ],
    "成皋": [
        {"target": "陈留", "hint": "往东传闻，陈留将有场大盟会，四方人马正往那赶"},
        {"target": "长安", "hint": "虎牢关守卒说，董卓已挟天子西迁长安"},
    ],
    "陈留": [
        {"target": "冀州", "hint": "北边传闻，袁绍在冀州广纳士人，盟主名头先到一步"},
        {"target": "汜水关", "hint": "西边关隘华雄叫阵，联军正愁没人出战"},
        {"target": "徐州", "hint": "东边传闻，徐州牧陶谦病重让城，刘备接了徐州印"},
    ],
    "长安": [
        {"target": "洛阳", "hint": "东边故都已被一把火烧成废墟"},
        {"target": "冀州", "hint": "河北袁绍正纠合诸侯"},
    ],
    "汜水关": [
        {"target": "陈留", "hint": "联军大营扎在陈留，十八路旗号都在那"},
        {"target": "成皋", "hint": "东边虎牢关的守军换成了西凉人"},
    ],
    "冀州": [
        {"target": "陈留", "hint": "南边传来诸侯在陈留会盟讨董的消息"},
        {"target": "洛阳", "hint": "洛阳正被董卓折腾得人心惶惶"},
        {"target": "许都", "hint": "南边许都，曹操挟天子令诸侯，天下士人趋之若鹜"},
        {"target": "官渡", "hint": "南边官渡，袁本初七十万大军正磨刀霍霍"},
    ],
    "许都": [
        {"target": "徐州", "hint": "东边徐州，刘备新领州牧，吕布暂驻小沛"},
        {"target": "洛阳", "hint": "西边故都洛阳，一片焦土废墟"},
        {"target": "官渡", "hint": "北边官渡，曹操与袁绍正陈兵对峙，大战一触即发"},
        {"target": "荆州", "hint": "南边荆州，刘表坐镇，刘备新投之"},
    ],
    "徐州": [
        {"target": "小沛", "hint": "徐州北边有座小沛城，刘备曾屯驻，如今归了吕布"},
        {"target": "许都", "hint": "西边许都是天子脚下，曹操挟天子令诸侯"},
    ],
    "小沛": [
        {"target": "许都", "hint": "往西过陈留便是许都，天子脚下"},
        {"target": "徐州", "hint": "徐州城就在东边，如今是吕布的地盘"},
    ],
    "官渡": [
        {"target": "许都", "hint": "南边许都，曹操大营粮草辎重皆在此"},
        {"target": "冀州", "hint": "北边冀州，袁绍七十万大军正虎视眈眈"},
    ],
    "荆州": [
        {"target": "许都", "hint": "北边许都，曹操挟天子令诸侯"},
        {"target": "官渡", "hint": "北边官渡，曹袁正决战"},
        {"target": "南郡", "hint": "东边南郡，周瑜正与曹仁争夺"},
        {"target": "赤壁", "hint": "东边赤壁，曹军铁锁连船，大战一触即发"},
    ],
    "南郡": [
        {"target": "荆州", "hint": "西边荆州，刘备新得之地"},
        {"target": "赤壁", "hint": "南边赤壁，火烧后的焦土战场"},
        {"target": "麦城", "hint": "北边麦城，关羽北伐的据点"},
    ],
    "赤壁": [
        {"target": "南郡", "hint": "北边南郡，周瑜曹仁正相持"},
        {"target": "荆州", "hint": "西边荆州，诸葛亮正布置地盘"},
    ],
    "益州": [
        {"target": "成都", "hint": "西边成都，刘璋坐镇天府之国"},
        {"target": "荆州", "hint": "东边荆州，刘备正盯着益州"},
    ],
    "成都": [
        {"target": "益州", "hint": "成都正是益州腹心，刘璋的都城"},
        {"target": "汉中", "hint": "北边汉中，张鲁占据着"},
    ],
    "合肥": [
        {"target": "荆州", "hint": "西边荆州，孙权正惦记着"},
        {"target": "南郡", "hint": "南边南郡，江东与曹魏拉锯"},
    ],
    "汉中": [
        {"target": "成都", "hint": "南边成都，刘备已得益州，正图汉中"},
        {"target": "益州", "hint": "益州门户，得汉中者得蜀地咽喉"},
    ],
    "麦城": [
        {"target": "南郡", "hint": "南边南郡，关羽北伐后路已断"},
        {"target": "荆州", "hint": "西边荆州，关羽最后的据点"},
    ],
}


def match_location(action: str) -> str | None:
    """解析地点动作：「前往/赶路到/动身去/去/回 地点」→ 地点名（未知地点返回 None）。

    句内匹配（与 world.action_days 同款）："我想去洛阳"这类自由输入也能命中，
    保证赶路耗时与目标地点判定一致（此前前缀式把句内地点判为"不移动"，扣了赶路时间却原地不动）。
    只认 LOCATIONS 已知地点名；非地点动作（"去打听消息"等）返回 None。
    解锁/推进判定在 director（有 registry flow），这里只管文本 → 地点名。
    """
    import re
    a = (action or "").strip()
    if not a:
        return None
    # 方向词 + 地点名句内匹配（去/往/到/赴/奔/进/入/回/返，与 world.action_days 同款；按 LOCATIONS 顺序首中）
    for name in LOCATIONS:
        if re.search(r"(?:去|往|到|赴|奔|进|入|回|返)" + re.escape(name), a):
            return name
    return None


def _load_json(path: str, cache: dict, key: str) -> dict:
    """mtime 缓存加载（JSON 文件变了就重读，开发期免重启）"""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return cache.get(key) or {}
    if key not in cache or cache[key].get("_mtime") != mtime:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            cache[key] = {"_mtime": mtime, "data": data}
        except (OSError, json.JSONDecodeError):
            pass
    return (cache.get(key) or {}).get("data") or {}


_timeline_cache: dict = {}
_normal_cache: dict = {}


def load_timeline() -> list[dict]:
    """加载全部时间线事件（按日期排序）"""
    events = []
    for i in range(1, 5):
        path = os.path.join(_DATA_DIR, "history_timeline", f"history_timeline_{i}.json")
        d = _load_json(path, _timeline_cache, f"tl{i}")
        events.extend(d.get("events", []))
    events.sort(key=lambda e: e.get("date", ""))
    return events


def load_normal(phase_idx: int) -> dict:
    """加载某阶段（1-6）的常态设定"""
    if not 1 <= phase_idx <= 6:
        return {}
    path = os.path.join(_DATA_DIR, "world_normal", f"world_normal_{phase_idx}.json")
    return _load_json(path, _normal_cache, f"n{phase_idx}")


def phase_of(world_date: dict) -> int:
    """玩家日期 → 阶段序号（1-6）。缺省回退 1。"""
    y = int(world_date.get("year", 0) or 0)
    m = int(world_date.get("month", 1) or 1)
    key = f"{y:03d}-{m:02d}"
    for p in PHASES:
        if _ym(p["start"]) <= (y, m) <= _ym(p["end"]):
            return p["idx"]
    # 超出阶段范围：最早回退 1，最晚回退 6
    if (y, m) < _ym(PHASES[0]["start"]):
        return 1
    return 6


def events_around(world_date: dict, days_before: int = 0) -> list[dict]:
    """取玩家当前日期附近的近期事件（用于场景注入/简报）。
    时间线只有年月粒度，取"同月或之前最近 N 条"。
    """
    y = int(world_date.get("year", 0) or 0)
    m = int(world_date.get("month", 1) or 1)
    cur = (y, m)
    events = load_timeline()
    near = [e for e in events if _ym(e.get("date", "")) <= cur]
    return near[-days_before:] if days_before > 0 else near[-3:]  # 默认最近 3 条


def world_context(world_date: dict, location: str = "") -> dict:
    """综合：当前阶段常态 + 近期事件 → 供 writer 注入的"当前世界背景"。

    返回 {phase_name, normal(五维), recent_events, location_normal}
    """
    idx = phase_of(world_date)
    normal = load_normal(idx)
    recent = events_around(world_date, days_before=3)
    loc_normal = None
    for loc in (normal.get("locations") or []):
        ln = loc.get("name") or ""
        # era.location 如 "颍川·荒野" → 匹配常态地点 "颍川"（name 作子串匹配）
        if ln and (ln == location or (location and ln in location)):
            loc_normal = loc
            break
    return {
        "phase_name": normal.get("phase", ""),
        "phase_idx": idx,
        "normal": normal,
        "recent_events": recent,
        "location_normal": loc_normal,
    }


# ═════════ 角色卡加载（自由大世界 · 决策7 角色性格驱动）═════════
# knowledge/characters/*.json（14 张角色卡）——writer 人设接线的数据源，替代硬编码 PERSONA_*。
_character_cache: dict = {}


def _char_file(name: str) -> str:
    """角色名 → characters/{name}.json 路径（拼音文件名映射）。"""
    import os
    mapping = {
        "曹操": "cao_cao", "刘备": "liu_bei", "关羽": "guan_yu", "张飞": "zhang_fei",
        "诸葛亮": "zhu_ge_liang", "司马懿": "si_ma_yi", "吕布": "lu_bu", "董卓": "dong_zhuo",
        "袁绍": "yuan_shao", "孙权": "sun_quan", "周瑜": "zhou_yu", "陈宫": "chen_gong",
        "王允": "wang_yun", "荀彧": "xun_yu",
        "孙坚": "sun_jian", "袁术": "yuan_shu", "貂蝉": "diao_chan", "华雄": "hua_xiong",
    }
    base = mapping.get(name, "")
    return os.path.join(_DATA_DIR, "characters", f"{base}.json") if base else ""


def load_character(name: str) -> dict:
    """读单个角色卡（mtime 缓存）。无卡/加载失败 → {}。"""
    path = _char_file(name)
    if not path:
        return {}
    return _load_json(path, _character_cache, name) or {}


def load_all_characters() -> dict:
    """读全部角色卡（14 张）。返回 {角色名: 卡}。"""
    out = {}
    for name in ("曹操", "刘备", "关羽", "张飞", "诸葛亮", "司马懿", "吕布", "董卓",
                 "袁绍", "孙权", "周瑜", "陈宫", "王允", "荀彧"):
        c = load_character(name)
        if c:
            out[name] = c
    return out
