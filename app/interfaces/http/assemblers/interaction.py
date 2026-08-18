from __future__ import annotations

import base64
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.interfaces.http.schemas.interaction import (
    InteractionAssessmentResponse,
    InteractionConfirmationRequest,
    InteractionGatewayResponse,
    InteractionIntentRequest,
    InteractionProposalResponse,
)
from app.modules.interaction.application.chat_stream import InteractionChatStreamCommand
from app.modules.interaction.application.gateway import (
    GatewayConfirmationCommand,
    GatewayRecognitionCommand,
    GatewayResult,
)
from app.modules.interaction.domain.confirmation import ConfirmationProposal
from app.modules.interaction.domain.intent import IntentAssessment
from app.modules.security.domain.principal import RequestPrincipal


def recognition_command(
    request: InteractionIntentRequest,
    principal: RequestPrincipal,
) -> GatewayRecognitionCommand:
    return GatewayRecognitionCommand(
        user_input=request.user_input,
        principal=principal,
        provided_inputs=dict(request.provided_inputs),
    )


def chat_stream_command(
    request: InteractionIntentRequest,
    principal: RequestPrincipal,
) -> InteractionChatStreamCommand:
    return InteractionChatStreamCommand(
        user_input=request.user_input,
        principal=principal,
        provided_inputs=dict(request.provided_inputs),
    )


def confirmation_command(
    proposal_id: str,
    request: InteractionConfirmationRequest,
    principal: RequestPrincipal,
) -> GatewayConfirmationCommand:
    return GatewayConfirmationCommand(
        proposal_id=proposal_id,
        action=request.action,
        principal=principal,
    )


def gateway_response(result: GatewayResult) -> InteractionGatewayResponse:
    execution_result = _json_object(result.execution_result)
    return InteractionGatewayResponse(
        status=result.status,
        message=result.message,
        assessment=_assessment_response(result.assessment),
        proposal=_proposal_response(result.proposal),
        execution_result=execution_result,
        error_code=result.error_code,
    )


def _json_object(value: object | None) -> dict[str, Any] | None:
    if value is None:
        return None
    encoded = jsonable_encoder(
        value,
        custom_encoder={
            bytes: lambda content: base64.b64encode(content).decode("ascii"),
        },
    )
    return encoded if isinstance(encoded, dict) else {"value": encoded}


def _proposal_response(
    proposal: ConfirmationProposal | None,
) -> InteractionProposalResponse | None:
    if proposal is None:
        return None
    return InteractionProposalResponse(
        proposal_id=proposal.proposal_id,
        state=proposal.state,
        capability_code=proposal.capability_code,
        summary=proposal.summary,
        confirmation_prompt=proposal.confirmation_prompt,
    )


def _assessment_response(
    assessment: IntentAssessment | None,
) -> InteractionAssessmentResponse | None:
    if assessment is None:
        return None
    return InteractionAssessmentResponse(
        status=assessment.status,
        capability_code=assessment.capability_code,
        missing_fields=list(assessment.missing_fields),
        clarification=assessment.clarification,
        confidence=assessment.confidence,
        error_code=assessment.error_code,
    )
