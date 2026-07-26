import json
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import save_world, get_all_worlds, get_world_graph

router = APIRouter()


class WorldCreate(BaseModel):
    name: str
    tagline: str
    concept: str
    graph: dict  # { nodes: [...], links: [...] }
    color: str = "#aabbff"


class WorldSummary(BaseModel):
    id: str
    name: str
    tagline: str
    concept: str
    color: str
    created_at: str


@router.post("/worlds", response_model=WorldSummary)
async def create_world(body: WorldCreate):
    world_id = f"custom_{uuid.uuid4().hex[:8]}"
    graph_json = json.dumps(body.graph, ensure_ascii=False)
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
