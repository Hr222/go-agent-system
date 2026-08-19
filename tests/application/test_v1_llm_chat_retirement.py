from fastapi.testclient import TestClient

from app.main import create_app


def test_v1_llm_chat_routes_are_not_registered() -> None:
    application = create_app()

    with TestClient(application) as client:
        sync_response = client.post("/api/v1/llm/chat", json={"message": "你好"})
        stream_response = client.post(
            "/api/v1/llm/chat/stream",
            json={"message": "你好"},
        )

    assert sync_response.status_code == 404
    assert stream_response.status_code == 404


def test_v2_interaction_chat_stream_remains_the_registered_chat_entry() -> None:
    application = create_app()

    with TestClient(application) as client:
        response = client.post("/api/v1/interaction/chat/stream", json={})

    assert response.status_code == 422
