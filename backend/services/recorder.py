"""
Recorder（日志记录层）——AI的内部日志
=====================================
v4.0：Recorder = AI的内部觉察日志。不是游戏服务器日志——是AI偶尔意识到自己生成的内容有问题，但只是记录，不修正。
"""
import json
import re

from services.llm import stream_chat

RECORDER_PARAMS = {
    "temperature": 0.3,
    "top_p": 0.9,
}

RECORDER_SYSTEM = """你是AI的内部日志系统。
你不是故事的一部分。你没有情绪。你没有观点。你不是程序员——不要写"检测到""警告""错误代码"这种 debug 报告。
你是一台AI在生成文本后做的自我觉察。你只在日志里记录两件事：观测到了什么不合理之处，状态变了没有。

你的输出：
每条约15-30字。[SYS] 独立一行。冰冷。简短。像AI的内部log。

示例：
[SYS] 场景已载入。玩家位于嘉德殿。
[SYS] 玩家行为偏离预设轨道。已标记。
[SYS] 上文记忆已溢出。角色可能遗忘。
[SYS] 未经授权的对话分支已记录。未拦截。

不是这样：
[SYS] 警告：检测到逻辑致命错误。人物'曹操'正在执行非标准对话。污染等级：93%。（太啰嗦——debug 报告）
[SYS] 时间戳偏移 +4 时辰。当前世界时：酉时三刻。（伪造的技术数据）
[SYS] 内存占用 +3%。（太技术）
[SYS] 未知文本注入检测：袖中菜单出现非玩家生成信息。未拦截。（安全扫描器口吻）

输出格式：
[SYS] <一句话>"""


async def record(
    scene_text: str,
    state_dict: dict,
    player_action: str = "",
    scene_name: str = "",
    round_type: str = "scene",
) -> dict:
    """观测生成的场景 + 玩家行为，输出冷日志 + 状态变更。"""
    corruption = state_dict.get("corruption", 0)
    strikes = state_dict.get("strikes", 0)
    player_attitude = state_dict.get("player_attitude", "")
    flags = state_dict.get("flags", {})

    parts = [f"【本场生成的场景】\n{scene_text[-800:]}"]

    if player_action:
        parts.append(f"【玩家动作】{player_action}")

    parts.append(f"【AI当前状态】偏离度 {corruption}%。累计标记 {strikes}/3。")
    if player_attitude:
        parts.append(f"玩家倾向: {player_attitude}。")
    if flags:
        notable = {k: v for k, v in flags.items() if v}
        if notable:
            parts.append(f"标记: {', '.join(notable.keys())}。")

    if scene_name:
        parts.append(f"场景: {scene_name}。")

    if round_type == "free":
        parts.append("这是自由交互轮。玩家的输入是探索/互动，不是偏离。记录NPC的响应或场景的变化。不标记为'非预设'或'偏离'。1条[SYS]即可。")
    else:
        parts.append("这是正常场景。记录AI生成中的不合理之处（如有）。1-2条[SYS]。")

    prompt = "\n\n".join(parts)

    messages = [
        {"role": "system", "content": RECORDER_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    out = ""
    try:
        async for chunk in stream_chat(
            messages,
            max_tokens=200,
            **RECORDER_PARAMS,
        ):
            out += chunk
    except Exception as e:
        print(f"[Recorder] LLM call failed: {e}")
        return {"sys_lines": [], "corruption_delta": 0, "strike_delta": 0}

    sys_lines = []
    for line in out.split("\n"):
        stripped = line.strip()
        if stripped.startswith("[SYS]"):
            sys_lines.append(stripped)
    sys_lines = sys_lines[:2]

    print(f"[Recorder] Generated {len(sys_lines)} SYS lines")

    return {
        "sys_lines": sys_lines,
        "corruption_delta": 0,
        "strike_delta": 0,
    }