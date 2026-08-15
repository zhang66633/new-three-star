"""
故事状态（Phase 2）——代码持有的唯一真相源
========================================
beat_index（下一要演的节拍）和 items（锁定道具表）只由代码读写，
LLM 无权变更。状态随请求往返（无状态 API，前端持有并回传）。
"""
from dataclasses import dataclass, field, asdict


@dataclass
class StoryState:
    node: str = ""                 # 当前节点，如 "曹操献刀"
    scene_index: int = 0           # 下一要演的场景/节拍下标（0基），只由代码推进
    beat_index: int = 0            # v3 兼容别名：与 scene_index 等价
    items: dict = field(default_factory=dict)
    #   锁定道具表：{"七星宝刀": {"owner": "王允", "locked": True, "desc": "..."}}
    facts: list = field(default_factory=list)   # 已成立的事实（供后续拍引用）
    identity: str = ""             # 玩家身份（仆役/武将/谋士...）
    turn: int = 0                  # 回合数
    roam_turns: int = 0            # 节点间漫游：0=不在漫游；>0=漫游中（已完成的漫游轮数）

    # ---- v3.2 选择追踪与叙事状态（Ink 式 state-accumulation） ----
    choice_history: list = field(default_factory=list)  # [{turn, action, scene, node}]
    flags: dict = field(default_factory=dict)           # 叙事旗标 {"defied_dong_zhuo": True}
    corruption: int = 0             # 世界腐败度 0-100，影响输出风格
    player_attitude: str = ""       # 玩家倾向：aggressive/diplomatic/cautious/chaotic
    strikes: int = 0                # 干扰剧情的次数，累计3次被踢出游戏

    def __post_init__(self):
        """保持 beat_index 与 scene_index 同步。"""
        if self.scene_index == 0 and self.beat_index != 0:
            self.scene_index = self.beat_index
        elif self.beat_index == 0 and self.scene_index != 0:
            self.beat_index = self.scene_index

    def to_dict(self) -> dict:
        d = asdict(self)
        # 兼容旧客户端：同时输出两个字段
        d["beat_index"] = self.scene_index
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StoryState":
        d = d or {}
        base = cls()
        si = int(d.get("scene_index", d.get("beat_index", base.scene_index)) or 0)
        bi = int(d.get("beat_index", d.get("scene_index", base.beat_index)) or 0)
        idx = si or bi  # 取非零值
        return cls(
            node=d.get("node", base.node),
            scene_index=idx,
            beat_index=idx,
            items=d.get("items", {}) or {},
            facts=d.get("facts", []) or [],
            identity=d.get("identity", base.identity),
            turn=int(d.get("turn", base.turn) or 0),
            roam_turns=int(d.get("roam_turns", base.roam_turns) or 0),
            # v3.2 新增字段
            choice_history=d.get("choice_history", []) or [],
            flags=d.get("flags", {}) or {},
            corruption=int(d.get("corruption", base.corruption) or 0),
            player_attitude=d.get("player_attitude", base.player_attitude) or "",
            strikes=int(d.get("strikes", base.strikes) or 0),
        )
