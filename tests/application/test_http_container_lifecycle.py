from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from app import main
from app.interfaces.http import dependencies


class TrackingContainer:
    instances: list[TrackingContainer] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.closed = False
        self.instances.append(self)

    async def aclose(self) -> None:
        self.closed = True


def test_request_container_closes_after_plain_and_streaming_responses(
    monkeypatch,
) -> None:  # noqa: ANN001
    TrackingContainer.instances.clear()
    monkeypatch.setattr(dependencies, "ApplicationContainer", TrackingContainer)
    application = FastAPI()
    application.dependency_overrides[dependencies.get_db_session] = lambda: object()
    application.dependency_overrides[dependencies.get_attachment_storage] = lambda: object()

    @application.get("/plain")
    async def plain_response(
        container=Depends(dependencies.get_application_container),  # noqa: ANN001
    ) -> dict[str, bool]:
        return {"closed_during_response": container.closed}

    @application.get("/stream")
    async def stream_response(
        container=Depends(dependencies.get_application_container),  # noqa: ANN001
    ) -> StreamingResponse:
        async def events():
            assert container.closed is False
            yield "event: complete\ndata: {}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    with TestClient(application) as client:
        plain = client.get("/plain")
        stream = client.get("/stream")

    assert plain.json() == {"closed_during_response": False}
    assert stream.text == "event: complete\ndata: {}\n\n"
    assert [container.closed for container in TrackingContainer.instances] == [True, True]


def test_request_container_releases_resources_when_dependency_generator_closes(
    monkeypatch,
) -> None:  # noqa: ANN001
    TrackingContainer.instances.clear()
    monkeypatch.setattr(dependencies, "ApplicationContainer", TrackingContainer)

    async def close_dependency() -> None:
        dependency = dependencies.get_application_container(
            session=object(),
            attachment_storage=object(),
        )
        container = await anext(dependency)
        assert container.closed is False
        await dependency.aclose()

    asyncio.run(close_dependency())

    assert len(TrackingContainer.instances) == 1
    assert TrackingContainer.instances[0].closed is True


def test_application_lifespan_releases_the_stateless_container(
    monkeypatch,
) -> None:  # noqa: ANN001
    class StatelessContainerProvider:
        def __init__(self) -> None:
            self.container = TrackingContainer()
            self.cache_cleared = False

        def __call__(self) -> TrackingContainer:
            return self.container

        def cache_clear(self) -> None:
            self.cache_cleared = True

    provider = StatelessContainerProvider()
    monkeypatch.setattr(main, "get_stateless_application_container", provider)
    monkeypatch.setattr(
        main,
        "inspect_knowledge_base_schema",
        lambda: SimpleNamespace(missing_tables=None),
    )

    with TestClient(main.create_app()):
        pass

    assert provider.container.closed is True
    assert provider.cache_cleared is True
