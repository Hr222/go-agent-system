from __future__ import annotations

import asyncio
import threading

from app.interfaces.http.routes.interaction import confirm_intent_proposal, recognize_intent
from app.interfaces.http.schemas.interaction import (
    InteractionConfirmationRequest,
    InteractionIntentRequest,
)
from app.platform.interaction.application.gateway import GatewayResult
from app.platform.security.domain.principal import RequestPrincipal


class BlockingGateway:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def recognize(self, command):  # noqa: ANN001
        del command
        self.started.set()
        self.release.wait(timeout=1)
        return GatewayResult(status="needs_clarification", message="需要补充信息。")

    def confirm(self, command):  # noqa: ANN001
        del command
        self.started.set()
        self.release.wait(timeout=1)
        return GatewayResult(status="cancelled", message="已取消。")


def _principal() -> RequestPrincipal:
    return RequestPrincipal.anonymous()


def test_intent_route_runs_blocking_gateway_off_event_loop() -> None:
    gateway = BlockingGateway()
    request = InteractionIntentRequest(user_input="你好", provided_inputs={})

    async def scenario() -> object:
        operation = asyncio.create_task(recognize_intent(request, gateway, _principal()))
        assert await asyncio.to_thread(gateway.started.wait, 1)
        heartbeat = asyncio.Event()
        asyncio.get_running_loop().call_soon(heartbeat.set)
        await asyncio.wait_for(heartbeat.wait(), timeout=0.2)
        gateway.release.set()
        return await operation

    result = asyncio.run(scenario())

    assert result.status == "needs_clarification"


def test_confirmation_route_runs_blocking_gateway_off_event_loop() -> None:
    gateway = BlockingGateway()
    request = InteractionConfirmationRequest(action="cancel")

    class NoAgentApplication:
        async def confirm_agent(self, command):  # noqa: ANN001
            del command
            return None

    async def scenario() -> object:
        operation = asyncio.create_task(
            confirm_intent_proposal(
                "proposal-1",
                request,
                NoAgentApplication(),
                gateway,
                _principal(),
            )
        )
        assert await asyncio.to_thread(gateway.started.wait, 1)
        heartbeat = asyncio.Event()
        asyncio.get_running_loop().call_soon(heartbeat.set)
        await asyncio.wait_for(heartbeat.wait(), timeout=0.2)
        gateway.release.set()
        return await operation

    result = asyncio.run(scenario())

    assert result.status == "cancelled"
