import json
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from db import save_world, get_all_worlds, get_world_graph

router = APIRouter()


class WorldCreate(BaseModel):
    # 长度钳制：防超大 body 膨胀 LLM token 成本 / 撑大 DB 行（nginx 1MB 是唯一软上限）
    name: str = Field(min_length=1, max_length=80)
    tagline: str = Field(max_length=200)
    concept: str = Field(max_length=2000)
    graph: dict  # { nodes: [...], links: [...] }
    color: str = Field(default="#aabbff", max_length=16)


class WorldSummary(BaseModel):
    id: str
    name: str
    tagline: str
    concept: str
    color: str
    created_at: str


@router.post("/worlds", response_model=WorldSummary)
async def create_world(body: WorldCreate):
    # graph 体积上限：节点/连线各限 200、序列化 ≤50KB（防超大图撑大 DB 行 / 膨胀 LLM 成本）
    nodes = body.graph.get("nodes") or []
    links = body.graph.get("links") or []
    if len(nodes) > 200 or len(links) > 200:
        raise HTTPException(status_code=400, detail="graph nodes/links 各限 200")
    graph_json = json.dumps(body.graph, ensure_ascii=False)
    if len(graph_json) > 50_000:
        raise HTTPException(status_code=400, detail="graph 体积过大")
    world_id = f"custom_{uuid.uuid4().hex[:8]}"
    await save_world(world_id, body.name, body.tagline, body.concept, graph_json, body.color)
    return {
        "id": world_id,
        "name": body.name,
        "tagline": body.tagline,
        "concept": body.concept,
        "color": body.color,
        "created_at": datetime.now().isoformat(),
    }


@router.get("/worlds")
async def list_worlds():
    return await get_all_worlds()


@router.get("/worlds/{world_id}/graph")
async def world_graph(world_id: str):
    graph_json = await get_world_graph(world_id)
    if not graph_json:
        raise HTTPException(status_code=404, detail="World not found")
    return json.loads(graph_json)
