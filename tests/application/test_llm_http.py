from __future__ import annotations

from fastapi.testclient import TestClient

from app.interfaces.http.dependencies import get_chat_application
from app.main import create_app
from app.modules.llm.application.chat import ChatApplication
from app.modules.llm.contracts import ChatLlmResult
from app.shared.exceptions import ServiceNotConfiguredError, UpstreamServiceError


class FakeChatLlm:
    def __init__(self, result: ChatLlmResult | None = None) -> None:
        self.result = result or ChatLlmResult(
            content="收到：你好",
            model="glm-test",
            prompt_version="llm-chat-v1",
            total_tokens=8,
        )
        self.requests = []

    def invoke(self, request):  # noqa: ANN001
        self.requests.append(request)
        return self.result


class RaisingChatLlm:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def invoke(self, request):  # noqa: ANN001
        self.calls += 1
        raise self.error


def test_llm_chat_http_route_returns_single_turn_response() -> None:
    application = create_app()
    application.dependency_overrides[get_chat_application] = lambda: ChatApplication(FakeChatLlm())

    response = TestClient(application).post(
        "/api/v1/llm/chat",
        json={"message": "你好"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "收到：你好",
        "model": "glm-test",
        "prompt_version": "llm-chat-v1",
        "usage": {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": 8,
        },
    }
    application.dependency_overrides.clear()


def test_llm_chat_http_route_rejects_blank_message() -> None:
    application = create_app()

    response = TestClient(application).post(
        "/api/v1/llm/chat",
        json={"message": ""},
    )

    assert response.status_code == 422


def test_llm_chat_http_rejects_overlong_message() -> None:
    application = create_app()

    response = TestClient(application).post(
        "/api/v1/llm/chat",
        json={"message": "a" * 10_001},
    )

    assert response.status_code == 422


def test_llm_chat_http_rejects_whitespace_only_message_without_calling_llm() -> None:
    llm = FakeChatLlm()
    application = create_app()
    application.dependency_overrides[get_chat_application] = lambda: ChatApplication(llm)

    response = TestClient(application).post(
        "/api/v1/llm/chat",
        json={"message": "   \n\t"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "消息内容不能为空。"
    assert llm.requests == []
    application.dependency_overrides.clear()


def test_llm_chat_http_maps_missing_service_configuration_to_503() -> None:
    llm = RaisingChatLlm(ServiceNotConfiguredError("服务未配置。"))
    application = create_app()
    application.dependency_overrides[get_chat_application] = lambda: ChatApplication(llm)

    response = TestClient(application).post(
        "/api/v1/llm/chat",
        json={"message": "你好"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "服务未配置。"
    assert llm.calls == 1
    application.dependency_overrides.clear()


def test_llm_chat_http_maps_upstream_failure_to_502() -> None:
    llm = RaisingChatLlm(UpstreamServiceError("上游模型不可用。"))
    application = create_app()
    application.dependency_overrides[get_chat_application] = lambda: ChatApplication(llm)

    response = TestClient(application).post(
        "/api/v1/llm/chat",
        json={"message": "你好"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "上游模型不可用。"
    assert llm.calls == 1
    application.dependency_overrides.clear()


def test_llm_chat_http_maps_empty_model_response_to_502() -> None:
    llm = FakeChatLlm(
        ChatLlmResult(
            content="",
            model="glm-test",
            prompt_version="llm-chat-v1",
        )
    )
    application = create_app()
    application.dependency_overrides[get_chat_application] = lambda: ChatApplication(llm)

    response = TestClient(application).post(
        "/api/v1/llm/chat",
        json={"message": "你好"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM 返回了空响应。"
    application.dependency_overrides.clear()
