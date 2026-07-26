import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.framework_picker import load_framework
from services.prompt_builder import build_worldview_prompt, build_custom_prompt
from services.llm import stream_chat
from config import MAX_TOKENS_WORLDVIEW

router = APIRouter()


class ExpandRequest(BaseModel):
    event: str
    framework: str


class CustomRequest(BaseModel):
    concept: str
    event: str | None = None


@router.post("/worldview/expand")
async def expand_worldview(req: ExpandRequest):
    """Expand a verdict into full worldview document."""
    framework = load_framework(req.framework)
    messages = build_worldview_prompt(req.event, framework)

    async def generate():
        yield f"data: {json.dumps({'type': 'framework', 'id': framework['id'], 'name': framework['name']}, ensure_ascii=False)}\n\n"
        async for chunk in stream_chat(messages, max_tokens=MAX_TOKENS_WORLDVIEW):
            yield f"data: {json.dumps({'type': 'content', 'text': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/worldview/custom")
async def custom_worldview(req: CustomRequest):
    """Generate a brand new worldview from user concept."""
    messages = build_custom_prompt(req.concept, req.event)

    async def generate():
        yield f"data: {json.dumps({'type': 'framework', 'id': 'custom', 'name': req.concept}, ensure_ascii=False)}\n\n"
        async for chunk in stream_chat(messages, max_tokens=MAX_TOKENS_WORLDVIEW):
            yield f"data: {json.dumps({'type': 'content', 'text': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
