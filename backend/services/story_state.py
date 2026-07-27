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
    beat_index: int = 0            # 下一要演的节拍下标（0基），只由代码推进
    items: dict = field(default_factory=dict)
    #   锁定道具表：{"七星宝刀": {"owner": "王允", "locked": True, "desc": "..."}}
    facts: list = field(default_factory=list)   # 已成立的事实（供后续拍引用）
    identity: str = ""             # 玩家身份（仆役/武将/谋士...）
    turn: int = 0                  # 回合数
    roam_turns: int = 0            # 节点间漫游：0=不在漫游；>0=漫游中（已完成的漫游轮数）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StoryState":
        d = d or {}
        base = cls()
        return cls(
            node=d.get("node", base.node),
            beat_index=int(d.get("beat_index", base.beat_index) or 0),
            items=d.get("items", {}) or {},
            facts=d.get("facts", []) or [],
            identity=d.get("identity", base.identity),
            turn=int(d.get("turn", base.turn) or 0),
            roam_turns=int(d.get("roam_turns", base.roam_turns) or 0),
        )
