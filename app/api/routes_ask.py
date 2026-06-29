"""
app/api/routes_ask.py — POST /ask and POST /ask/stream endpoints.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_current_user
from app.api.schemas import AskRequest, AskResponse
from app.generation.answer_service import answer_question
from app.generation.streaming import stream_answer
from app.memory import add_chat_turn, get_history_as_dicts

router = APIRouter(tags=["ask"])


import json


@router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Any:
    """Non-streaming RAG answer endpoint."""
    session_id = request.session_id or str(uuid.uuid4())
    history = get_history_as_dicts(session_id)
    filters = request.filters.model_dump(exclude_none=True) if request.filters else {}
    result = await answer_question(
        request.question,
        session_id=session_id,
        conversation_history=history,
        top_k_context=request.top_k,
        filters=filters,
        user_role=current_user.get("role", "employee"),
        department=current_user.get("department", "general"),
        include_debug=request.include_debug,
    )
    if result.get("answerability") != "not_found":
        add_chat_turn(session_id, request.question, result["answer"])
    return result


@router.post("/ask/stream")
async def ask_stream(
    request: AskRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    """Streaming RAG answer endpoint — emits JSON-line SSE events."""
    session_id = request.session_id or str(uuid.uuid4())
    history = get_history_as_dicts(session_id)
    filters = request.filters.model_dump(exclude_none=True) if request.filters else {}

    async def event_generator():
        async for event in stream_answer(
            request.question,
            session_id=session_id,
            conversation_history=history,
            top_k_context=request.top_k,
            filters=filters,
            user_role=current_user.get("role", "employee"),
            department=current_user.get("department", "general"),
        ):
            yield event
            try:
                if event.strip():
                    evt_obj = json.loads(event.strip())
                    if evt_obj.get("event") == "final_sources":
                        data = evt_obj.get("data", {})
                        ans = data.get("answer", "")
                        ans_ability = data.get("answerability", "")
                        if ans and ans_ability != "not_found":
                            add_chat_turn(session_id, request.question, ans)
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
