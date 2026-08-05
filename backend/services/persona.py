"""
Persona（角色人设系统）
=======================
v1.0：每角色一份结构化人设。引擎按需查询，注入行为引导到 Context。

职责：
1. 加载角色人设
2. 根据场景和玩家动作生成行为引导
3. 输出游戏化解读
"""
import json
import os

PERSONA_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge", "characters")

# 缓存
_cache: dict[str, dict] = {}


def load(name: str) -> dict | None:
    """加载角色人设。接受中文名或拼音文件名。"""
    if name in _cache:
        return _cache[name]

    # 1. 直接匹配
    path = os.path.join(PERSONA_DIR, f"{name}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _cache[name] = data
            return data
        except Exception:
            return None

    # 2. 遍历文件按 name 字段匹配
    if os.path.exists(PERSONA_DIR):
        for fname in os.listdir(PERSONA_DIR):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(PERSONA_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            if data.get("name") == name or data.get("courtesy") == name:
                _cache[name] = data
                _cache[fname] = data  # 双向缓存
                return data

    return None


def get_behavior_guide(name: str, action: str = "") -> str:
    """根据角色人设和玩家动作，生成一句话行为引导。

    示例：
    - 玩家"阻止曹操" → "曹操被阻止时先质疑动机。被轻视的触发点被激活——'连你也想把我排除在外？'"
    - 玩家"跟着曹操" → "曹操察觉被跟随时会主动制造互动——回头说一句让你站不稳的话。"
    """
    data = load(name)
    if not data:
        return ""

    rules = data.get("behavior_rules", {})
    action_lower = action.lower()

    # 匹配行为规则
    if any(k in action_lower for k in ["阻止", "拦住", "拦下", "挡住", "不让", "劝", "拉住"]):
        guide = rules.get("when_player_blocks", "")
    elif any(k in action_lower for k in ["跟着", "尾随", "追踪", "跟随", "追"]):
        guide = rules.get("when_player_follows", "")
    elif any(k in action_lower for k in ["杀", "刺", "攻击", "威胁", "动手", "拔刀"]):
        guide = rules.get("when_player_threatens", "")
    elif any(k in action_lower for k in ["夸", "赞", "奉承", "佩服", "拜见", "仰慕"]):
        guide = rules.get("when_player_flatters", "")
    elif not action:
        guide = rules.get("when_player_ignores", "")
    else:
        guide = ""

    if guide:
        return f"{name}：{guide}"

    # 兜底：返回说话风格
    speech = data.get("speech", {})
    return f"{name}：{speech.get('style', '')}"


def get_speech_guide(name: str) -> str:
    """获取角色说话风格引导。"""
    data = load(name)
    if not data:
        return ""
    speech = data.get("speech", {})
    parts = [speech.get("style", "")]
    bugs = speech.get("bugs", [])
    if bugs:
        parts.append("可出现的bug：" + " / ".join(bugs[:2]))
    return " ".join(p for p in parts if p)


def get_game_interpretation(name: str) -> str:
    """获取角色的游戏化解读。给 Recorder/Interpreter 用的背景知识。"""
    data = load(name)
    if not data:
        return ""
    gi = data.get("game_interpretation", {})
    parts = [f"{name}：{gi.get('core', '')}"]
    for key, val in gi.items():
        if key != "core" and val:
            parts.append(f"  {key}：{val}")
    return "\n".join(parts)


def list_characters() -> list[str]:
    """列出所有可用角色。"""
    chars = []
    if os.path.exists(PERSONA_DIR):
        for fname in os.listdir(PERSONA_DIR):
            if fname.endswith(".json"):
                chars.append(os.path.splitext(fname)[0])
    return chars
