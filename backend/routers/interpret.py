import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.framework_picker import pick_random_framework, select_relevant_mechanisms, get_frameworks_list
from services.prompt_builder import build_verdict_prompt
from services.llm import stream_chat
from config import MAX_TOKENS_VERDICT

router = APIRouter()


class InterpretRequest(BaseModel):
    event: str
    framework: str | None = None


@router.post("/interpret")
async def interpret(req: InterpretRequest):
    """Generate a verdict card for the given event."""
    if req.framework:
        from services.framework_picker import load_framework
        framework = load_framework(req.framework)
    else:
        framework = pick_random_framework()

    mechanisms = select_relevant_mechanisms(req.event, framework)
    messages = build_verdict_prompt(req.event, framework, mechanisms)

    async def generate():
        # First send framework info
        yield f"data: {json.dumps({'type': 'framework', 'id': framework['id'], 'name': framework['name'], 'tagline': framework['tagline']}, ensure_ascii=False)}\n\n"
        # Stream content
        async for chunk in stream_chat(messages, max_tokens=MAX_TOKENS_VERDICT):
            yield f"data: {json.dumps({'type': 'content', 'text': chunk}, ensure_ascii=False)}\n\n"
        # Done
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/frameworks")
async def list_frameworks():
    """List all available frameworks."""
    return {"frameworks": get_frameworks_list()}
