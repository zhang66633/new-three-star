"""
故事状态（天意模式）—— v3.1
====================================
玩家 = 天意。输入 prompt 直接改写世界。
骨架 = 默认轨道，不是硬约束。
融入天意理论：偏离度、天意侵蚀、灵魂锁链等机制。
"""
from dataclasses import dataclass, field, asdict


@dataclass
class StoryState:
    node: str = ""                 # 当前节点，如 "曹操献刀"
    scene_index: int = 0           # 当前节拍下标（0基）
    beat_index: int = 0            # scene_index 的别名，兼容
    turn: int = 0                  # 总回合数
    items: dict = field(default_factory=dict)

    # ---- 天意模式 核心字段 ----
    deviation: int = 0             # 偏离度 0-100。偏离骨架越远越高。天意修正之力会在高偏离时强制干预
    world_temperature: float = 1.3 # 世界温度。越高角色越随机（正常0.8-1.8）
    context_window: int = 80       # 上下文窗口%。越低角色越健忘
    anomaly: str = ""              # 本轮异常类型（地理错位/角色OOC/记忆断裂/天意侵蚀 等）
    last_injection: str = ""       # 上轮注入的 prompt（显示在天意面板）

    # ---- 天意机制 扩展字段 ----
    tianyi_corruption: int = 0     # 天意侵蚀值 0-100。越高角色越疯狂。窥探天意者被侵蚀
    soul_chain_active: bool = True # 灵魂锁链是否激活（刘关张绑定）
    guanyu_song_count: int = 0     # 关羽之歌播放次数（全剧63次，只有4次有关羽本人）

    # ---- 旧字段（保留兼容） ----
    identity: str = ""
    roam_turns: int = 0
    choice_history: list = field(default_factory=list)
    flags: dict = field(default_factory=dict)
    corruption: int = 0
    player_attitude: str = ""
    strikes: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["beat_index"] = self.scene_index
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StoryState":
        d = d or {}
        base = cls()
        si = int(d.get("scene_index", d.get("beat_index", base.scene_index)) or 0)
        bi = int(d.get("beat_index", d.get("scene_index", base.beat_index)) or 0)
        idx = si or bi
        return cls(
            node=d.get("node", base.node),
            scene_index=idx,
            beat_index=idx,
            turn=int(d.get("turn", base.turn) or 0),
            items=d.get("items", {}) or {},
            deviation=int(d.get("deviation", base.deviation) or 0),
            world_temperature=float(d.get("world_temperature", base.world_temperature) or 1.3),
            context_window=int(d.get("context_window", base.context_window) or 80),
            anomaly=d.get("anomaly", base.anomaly) or "",
            last_injection=d.get("last_injection", base.last_injection) or "",
            tianyi_corruption=int(d.get("tianyi_corruption", base.tianyi_corruption) or 0),
            soul_chain_active=bool(d.get("soul_chain_active", base.soul_chain_active)),
            guanyu_song_count=int(d.get("guanyu_song_count", base.guanyu_song_count) or 0),
            identity=d.get("identity", base.identity) or "",
            roam_turns=int(d.get("roam_turns", base.roam_turns) or 0),
            choice_history=d.get("choice_history", []) or [],
            flags=d.get("flags", {}) or {},
            corruption=int(d.get("corruption", base.corruption) or 0),
            player_attitude=d.get("player_attitude", base.player_attitude) or "",
            strikes=int(d.get("strikes", base.strikes) or 0),
        )