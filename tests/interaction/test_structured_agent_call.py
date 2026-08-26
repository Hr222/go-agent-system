from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.platform.interaction import AgentCallError, AgentCallResult, StructuredAgentCall


def test_structured_agent_call_keeps_correlation_ids_and_is_serializable() -> None:
    call = StructuredAgentCall(
        call_id="call-1",
        capability_code="agent.tender.generate_bid_skeleton",
        inputs={"file_name": "招标文件.docx"},
        conversation_id="conversation-1",
        turn_id="turn-2",
        run_id="run-3",
        parent_run_id="run-1",
    )

    assert call.model_dump() == {
        "call_id": "call-1",
        "capability_code": "agent.tender.generate_bid_skeleton",
        "inputs": {"file_name": "招标文件.docx"},
        "conversation_id": "conversation-1",
        "turn_id": "turn-2",
        "run_id": "run-3",
        "parent_run_id": "run-1",
    }
    with pytest.raises(ValidationError):
        call.call_id = "call-2"  # type: ignore[misc]


def test_agent_call_contracts_reject_execution_fields_and_invalid_values() -> None:
    invalid_requests = (
        {"call_id": "call-1", "capability_code": "agent.test", "inputs": []},
        {
            "call_id": "call-1",
            "capability_code": "agent.test",
            "inputs": {},
            "dispatch_key": "agent.test",
        },
        {"call_id": " ", "capability_code": "agent.test", "inputs": {}},
        {"call_id": "call-1", "capability_code": " ", "inputs": {}},
    )

    for payload in invalid_requests:
        with pytest.raises(ValidationError):
            StructuredAgentCall.model_validate(payload)


def test_agent_call_result_and_error_keep_only_controlled_data() -> None:
    result = AgentCallResult(
        call_id="call-1",
        capability_code="agent.test",
        output={"status": "completed"},
        run_id="run-1",
    )
    error = AgentCallError(
        call_id="call-1",
        capability_code="agent.test",
        error_code="AGENT_TIMEOUT",
        message="Agent 处理超时，请稍后重试。",
        retryable=True,
        run_id="run-1",
    )

    assert result.output == {"status": "completed"}
    assert error.retryable is True
    assert error.model_dump(exclude_none=True)["error_code"] == "AGENT_TIMEOUT"

    for contract, forbidden in (
        (result, {"provider_response": {"raw": "secret"}}),
        (error, {"traceback": "internal details"}),
    ):
        with pytest.raises(ValidationError):
            type(contract).model_validate({**contract.model_dump(), **forbidden})


def test_agent_call_error_rejects_uncontrolled_error_codes_and_empty_messages() -> None:
    with pytest.raises(ValidationError):
        AgentCallError(
            call_id="call-1",
            capability_code="agent.test",
            error_code="provider.internal detail",
            message="失败",
        )
    with pytest.raises(ValidationError):
        AgentCallError(
            call_id="call-1",
            capability_code="agent.test",
            error_code="AGENT_FAILED",
            message=" ",
        )
