import json
import os
from config import KNOWLEDGE_DIR


def load_mechanisms() -> dict:
    path = os.path.join(KNOWLEDGE_DIR, "mechanisms.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_framework(framework_id: str) -> dict:
    # 路径遍历防护：只允许纯文件名
    if not framework_id:
        raise ValueError(f"Framework not found: {framework_id}")
    name = os.path.basename(framework_id)
    if name != framework_id or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"Framework not found: {framework_id}")
    path = os.path.join(KNOWLEDGE_DIR, "frameworks", f"{name}.json")
    if not os.path.exists(path):
        raise ValueError(f"Framework not found: {framework_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
