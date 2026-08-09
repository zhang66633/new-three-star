import json
import os
from services.framework_picker import load_mechanisms
from config import PROMPTS_DIR


def _load_prompt_template(name: str) -> str:
    path = os.path.join(PROMPTS_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _format_all_mechanisms() -> str:
    data = load_mechanisms()
    lines = []
    for cat in data["categories"]:
        lines.append(f"\n## {cat['name']}")
        for m in cat["mechanisms"]:
            effects = "、".join(m.get("effects", []))
            lines.append(f"- 【{m['name']}】{m['description']}（效果：{effects}）")
    return "\n".join(lines)


def build_worldview_prompt(event: str, framework: dict) -> list[dict]:
    """Build messages for full worldview expansion."""
    system_template = _load_prompt_template("worldview_system.txt")

    system_content = system_template.format(
        framework_name=framework["name"],
        framework_metaphor=framework["core_metaphor"],
        framework_tianyi=framework.get("tianyi_interpretation", ""),
        framework_points="\n".join(f"- {p}" for p in framework.get("key_points", [])),
        character_roles=json.dumps(framework.get("character_roles", {}), ensure_ascii=False, indent=2),
        all_mechanisms=_format_all_mechanisms(),
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"触发事件：{event}\n\n请展开完整世界观论述。"},
    ]


def build_custom_prompt(concept: str, event: str | None = None) -> list[dict]:
    """Build messages for custom worldview generation."""
    system_template = _load_prompt_template("custom_system.txt")

    # Use two existing frameworks as few-shot examples
    from services.framework_picker import load_framework
    try:
        example1 = load_framework("cthulhu")
        example2 = load_framework("game_world")
        examples = f"""【示例一：{example1['name']}】
核心隐喻：{example1['core_metaphor']}
天意本质：{example1.get('tianyi_interpretation', '')}
要点：
{chr(10).join('- ' + p for p in example1.get('key_points', [])[:4])}

【示例二：{example2['name']}】
核心隐喻：{example2['core_metaphor']}
天意本质：{example2.get('tianyi_interpretation', '')}
要点：
{chr(10).join('- ' + p for p in example2.get('key_points', [])[:4])}"""
    except Exception:
        examples = "（无可用示例）"

    system_content = system_template.format(
        all_mechanisms=_format_all_mechanisms(),
        examples=examples,
    )

    user_content = f"新世界观假说：{concept}"
    if event:
        user_content += f"\n（关联事件：{event}）"
    user_content += "\n\n请构建完整世界观。"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
