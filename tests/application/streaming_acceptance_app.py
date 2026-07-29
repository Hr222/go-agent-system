from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.composition import ApplicationContainer
from app.interfaces.http.dependencies import get_stateless_application_container
from app.main import create_app
from app.modules.llm.contracts import ChatLlmRequest, ChatLlmStreamChunk


class AcceptanceStreamingLlm:
    def stream(self, request: ChatLlmRequest) -> AsyncIterator[ChatLlmStreamChunk]:
        async def generate() -> AsyncIterator[ChatLlmStreamChunk]:
            yield ChatLlmStreamChunk(
                content="first",
                model="acceptance-glm",
                prompt_version=request.prompt_version,
            )
            await asyncio.sleep(1)
            yield ChatLlmStreamChunk(
                content="second",
                model="acceptance-glm",
                prompt_version=request.prompt_version,
                total_tokens=2,
            )

        return generate()


app = create_app()
container = ApplicationContainer(streaming_chat_llm=AcceptanceStreamingLlm())
app.dependency_overrides[get_stateless_application_container] = lambda: container
