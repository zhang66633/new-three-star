import json
import os
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.framework_picker import load_framework, load_all_frameworks, load_mechanisms
from services.llm import stream_chat
from config import KNOWLEDGE_DIR, MAX_TOKENS_WORLDVIEW

router = APIRouter()

# 机制类别 → 节点类型映射
CATEGORY_TYPE_MAP = {
    "A1": "tianyi",
    "A2": "spacetime",
    "A3": "military",
    "A4": "social",
    "A5": "character",
    "A6": "item",
    "A7": "spacetime",
    "A8": "creature",
}


@router.get("/graph/{framework_id}")
async def get_graph(framework_id: str):
    """Build graph data (nodes + links) for a worldview."""
    try:
        framework = load_framework(framework_id)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Framework not found: {framework_id}")
    mechanisms = load_mechanisms()

    nodes = []
    links = []

    # 从框架的character_roles生成角色节点
    for char_name, role_desc in framework.get("character_roles", {}).items():
        nodes.append({
            "id": f"char_{char_name}",
            "name": char_name,
            "type": "character",
            "summary": role_desc,
        })

    # 从机制库生成机制节点（选取与框架相关的）
    framework_keywords = set(framework.get("keywords", []))
    framework_points_text = " ".join(framework.get("key_points", []))

    for cat in mechanisms["categories"]:
        cat_type = CATEGORY_TYPE_MAP.get(cat["id"], "social")
        for mech in cat["mechanisms"]:
            # 相关性评分
            relevance = 0
            for kw in mech.get("keywords", []):
                if kw in framework_points_text:
                    relevance += 2
                if kw in framework_keywords:
                    relevance += 1
            # 天意机制始终包含
            if cat["id"] == "A1":
                relevance += 3

            if relevance >= 1:
                node_id = f"mech_{mech['id']}"
                nodes.append({
                    "id": node_id,
                    "name": mech["name"],
                    "type": cat_type,
                    "summary": mech["description"],
                })

                # 角色→机制连线（基于角色专属机制）
                if cat["id"] == "A5":
                    # 角色专属机制连到对应角色
                    char_name = mech["name"].split("·")[0] if "·" in mech["name"] else None
                    if char_name:
                        char_node_id = f"char_{char_name}"
                        if any(n["id"] == char_node_id for n in nodes):
                            links.append({
                                "source": char_node_id,
                                "target": node_id,
                                "relation": "专属机制",
                            })

    # 天意→其他机制的因果连线（天意连接所有高级机制）
    tianyi_nodes = [n for n in nodes if n["type"] == "tianyi"]
    other_nodes = [n for n in nodes if n["type"] != "tianyi" and n["type"] != "character"]
    if tianyi_nodes:
        tianyi_id = tianyi_nodes[0]["id"]
        for node in other_nodes[:8]:  # 天意连接前8个机制
            links.append({
                "source": tianyi_id,
                "target": node["id"],
                "relation": "天意驱动",
            })

    # 角色之间的连线（基于框架要点中的关系）
    char_nodes = [n for n in nodes if n["type"] == "character"]
    for i in range(len(char_nodes) - 1):
        links.append({
            "source": char_nodes[i]["id"],
            "target": char_nodes[i + 1]["id"],
            "relation": "命运交织",
        })

    return {"nodes": nodes, "links": links}


class NodeDiveRequest(BaseModel):
    framework_id: str = ""
    framework: str = ""
    node_name: str
    node_type: str = ""
    node_summary: str = ""


@router.post("/worldview/node-dive")
async def node_dive(req: NodeDiveRequest):
    """AI deep dive with B站解读风格."""
    fw_id = req.framework_id or req.framework
    framework = load_framework(fw_id)

    system_prompt = f"""你是一个B站新三国解读UP主，正在给观众讲解「{framework['name']}」世界观下的一个证据。

世界观核心：{framework['core_metaphor']}
天意本质：{framework.get('tianyi_interpretation', '')}

你的风格（模仿以下B站高赞评论的口吻）：
- "一句'记得给弟弟报仇'的亡语，就堵死了刘备用兄弟情为借口自刎归天的道路啊，刘备还想装聋来了句'云长你说什么？'假装没听到，但是他已经不敢赌系统判定了。"
- "你别说这个设定写小说挺有意思的。三个仇人，系统直接强制绑定灵魂锁链，然后老大赢的方式是自刎归天，老二老三的任务是阻止老大自刎归天。但是三个人关系很差又巴不得对方死。这设定好玩"
- "诸葛亮没有一丝被冤枉的样子，而是面无表情的整理着书卷，因为在诸葛亮的视角里，自己作为军师，任务之一还真就是帮刘备达成死亡结局，所以盼着刘备死还就那个理所应当。"
- "曹操一直以为自己能化龙，结果刘备先他一步通关，抬头一看刘备融入天意盯着自己笑呢"
- "刘备最后夷陵之战的时候问吴军在喊什么，听到'生擒陛下'的时候脸都黑了，因为他想死，生擒就全完了，所以急着和吴军拼了。结果还是因为众将太给力了没死成"

要求：
1. 150-300字，像在跟观众聊天一样讲清楚这个证据
2. 把剧情bug解读为"设定"，语气是"我彻底想明白了"的兴奋感
3. 可以用现代概念类比（游戏机制、编程、系统、进程等）
4. 可以引用新三国原台词作为佐证
5. 短句为主，偶尔长句分析。可以用"属于是""绷不住""你看""说白了"等口语
6. 不要学术腔，不要"首先其次最后"结构，不要emoji"""

    user_prompt = f"讲解这个证据：「{req.node_name}」——{req.node_summary}\n在「{framework['name']}」世界观下，这东西为什么存在？怎么运作的？细思极恐的点在哪？"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    async def generate():
        async for chunk in stream_chat(messages, max_tokens=800):
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


class CustomGraphRequest(BaseModel):
    concept: str


@router.post("/worldview/custom-graph")
async def custom_graph(req: CustomGraphRequest):
    """Generate a new worldview as graph nodes/links via SSE."""
    mechanisms = load_mechanisms()

    # 构建机制摘要供AI参考
    mech_summary = []
    for cat in mechanisms["categories"]:
        for m in cat["mechanisms"][:5]:
            mech_summary.append(f"- {m['name']}: {m['description']}")
    mech_text = "\n".join(mech_summary[:30])

    system_prompt = f"""你是新三国平行世界研究院的开创性学者。用户提出了一个全新世界观假说。
请基于新三国机制库构建一套完整世界观，并以JSON格式逐步输出节点和连线。

机制库参考：
{mech_text}

输出格式（严格按此格式，每行一个JSON）：
先输出所有节点（8-15个），再输出连线（6-12条）。

节点格式：NODE|{{"id":"唯一id","name":"名称","type":"类型","summary":"一句话描述"}}
类型可选：character, tianyi, spacetime, military, social, item, creature
角色节点用character，核心天意解释用tianyi，其余按内容分类。

连线格式：LINK|{{"source":"源id","target":"目标id","relation":"关系描述"}}

要求：
1. 必须包含至少1个tianyi节点（解释天意在该世界观下是什么）
2. 必须包含2-4个character节点（主要角色的新身份）
3. 必须包含4-8个机制节点（用新概念重新解释机制库中的机制）
4. 节点summary要体现该世界观的独特视角
5. 连线要体现因果/驱动关系
6. 直接输出，不要任何解释文字"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"新世界观假说：{req.concept}\n请构建节点和连线。"},
    ]

    async def generate():
        buffer = ""
        async for chunk in stream_chat(messages, max_tokens=8000):
            buffer += chunk
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line.startswith("NODE|"):
                    try:
                        node = json.loads(line[5:])
                        yield f"data: {json.dumps({'type': 'node', 'node': node}, ensure_ascii=False)}\n\n"
                    except json.JSONDecodeError:
                        pass
                elif line.startswith("LINK|"):
                    try:
                        link = json.loads(line[5:])
                        yield f"data: {json.dumps({'type': 'link', 'link': link}, ensure_ascii=False)}\n\n"
                    except json.JSONDecodeError:
                        pass
        # 处理buffer中剩余内容
        if buffer.strip().startswith("NODE|"):
            try:
                node = json.loads(buffer.strip()[5:])
                yield f"data: {json.dumps({'type': 'node', 'node': node}, ensure_ascii=False)}\n\n"
            except: pass
        elif buffer.strip().startswith("LINK|"):
            try:
                link = json.loads(buffer.strip()[5:])
                yield f"data: {json.dumps({'type': 'link', 'link': link}, ensure_ascii=False)}\n\n"
            except: pass
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
