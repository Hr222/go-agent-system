from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.interfaces.http.assemblers.interaction import (
    chat_stream_command,
    confirmation_command,
    gateway_response,
    recognition_command,
)
from app.interfaces.http.dependencies import (
    get_intent_interaction_gateway,
    get_interaction_chat_stream_application,
)
from app.interfaces.http.schemas.interaction import (
    InteractionChatRequest,
    InteractionConfirmationRequest,
    InteractionGatewayResponse,
    InteractionIntentRequest,
)
from app.interfaces.http.security import get_request_principal
from app.interfaces.http.streaming import serialize_sse_event
from app.platform.interaction.application.chat_stream import InteractionChatStreamApplication
from app.platform.interaction.application.gateway import IntentInteractionGateway
from app.platform.security.domain.principal import RequestPrincipal

router = APIRouter()


@router.post("/intent", response_model=InteractionGatewayResponse)
async def recognize_intent(
    request: InteractionIntentRequest,
    gateway: IntentInteractionGateway = Depends(get_intent_interaction_gateway),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> InteractionGatewayResponse:
    """识别能力并生成待确认提议，不执行任何业务目标。"""

    try:
        return gateway_response(gateway.recognize(recognition_command(request, principal)))
    except Exception as exc:  # noqa: BLE001 - HTTP boundary must not expose internals
        raise HTTPException(status_code=500, detail="统一交互入口暂时不可用。") from exc


@router.post("/chat/stream")
async def interaction_chat_stream(
    http_request: Request,
    request: InteractionChatRequest,
    application: InteractionChatStreamApplication = Depends(
        get_interaction_chat_stream_application
    ),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> StreamingResponse:
    """Route chat on the server and return only browser-safe interaction events."""

    preparation = application.prepare(chat_stream_command(request, principal))
    async def events() -> AsyncIterator[str]:
        async for event in application.stream(
            preparation,
            is_disconnected=http_request.is_disconnected,
        ):
            yield serialize_sse_event(event.name, event.data)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/proposals/{proposal_id}/confirmation",
    response_model=InteractionGatewayResponse,
)
async def confirm_intent_proposal(
    proposal_id: str,
    request: InteractionConfirmationRequest,
    application: InteractionChatStreamApplication = Depends(
        get_interaction_chat_stream_application
    ),
    gateway: IntentInteractionGateway = Depends(get_intent_interaction_gateway),
    principal: RequestPrincipal = Depends(get_request_principal),
) -> InteractionGatewayResponse:
    """消费一次待确认提议；确认后才可能调用固定分发目标。"""

    try:
        command = confirmation_command(proposal_id, request, principal)
        dialogue_result = application.confirm_agent(command)
        if dialogue_result is not None:
            return gateway_response(dialogue_result)
        return gateway_response(
            gateway.confirm(command)
        )
    except Exception as exc:  # noqa: BLE001 - HTTP boundary must not expose internals
        raise HTTPException(status_code=500, detail="统一交互入口暂时不可用。") from exc
