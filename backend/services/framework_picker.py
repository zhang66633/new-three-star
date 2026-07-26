import json
import os
import random
from config import KNOWLEDGE_DIR


def load_mechanisms() -> dict:
    path = os.path.join(KNOWLEDGE_DIR, "mechanisms.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_framework(framework_id: str) -> dict:
    path = os.path.join(KNOWLEDGE_DIR, "frameworks", f"{framework_id}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_frameworks() -> list[dict]:
    frameworks_dir = os.path.join(KNOWLEDGE_DIR, "frameworks")
    frameworks = []
    for filename in os.listdir(frameworks_dir):
        if filename.endswith(".json"):
            with open(os.path.join(frameworks_dir, filename), "r", encoding="utf-8") as f:
                frameworks.append(json.load(f))
    return frameworks


def pick_random_framework(exclude: str | None = None) -> dict:
    frameworks = load_all_frameworks()
    if exclude:
        frameworks = [f for f in frameworks if f["id"] != exclude]
    return random.choice(frameworks)


def select_relevant_mechanisms(event: str, framework: dict, count: int = 6) -> list[dict]:
    """Select mechanisms relevant to the event and framework."""
    data = load_mechanisms()
    all_mechs = []
    for category in data["categories"]:
        for mech in category["mechanisms"]:
            mech["_category"] = category["name"]
            all_mechs.append(mech)

    # Score by keyword overlap with event
    event_lower = event.lower()
    scored = []
    for mech in all_mechs:
        score = 0
        for kw in mech.get("keywords", []):
            if kw in event_lower:
                score += 2
        # Bonus for framework-related mechanisms
        for kw in framework.get("keywords", []):
            if kw in mech.get("description", ""):
                score += 1
        scored.append((score, mech))

    scored.sort(key=lambda x: -x[0])

    # Always include at least one A1 (天意) mechanism
    tianyi = [m for m in all_mechs if m["id"].startswith("A1")]
    selected = [tianyi[0]] if tianyi else []

    # Fill rest by relevance score
    for _, mech in scored:
        if mech not in selected:
            selected.append(mech)
        if len(selected) >= count:
            break

    return selected


def get_frameworks_list() -> list[dict]:
    """Return lightweight framework list for frontend."""
    frameworks = load_all_frameworks()
    return [
        {
            "id": f["id"],
            "name": f["name"],
            "tagline": f["tagline"],
            "suitable_scenes": f.get("suitable_scenes", []),
        }
        for f in frameworks
    ]
