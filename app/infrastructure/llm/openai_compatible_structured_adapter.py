from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.infrastructure.llm.structured_output_normalization import (
    NormalizingStructuredLlm,
    RawStructuredLlmResponse,
    SchemaAwareJsonStructuredOutputNormalizer,
    StructuredOutputNormalizer,
    raw_response_from_provider_response,
)
from app.modules.llm.contracts import StructuredLlmRequest
from app.shared.config import LlmProviderName, Settings, settings
from app.shared.exceptions import ServiceNotConfiguredError


class OpenAICompatibleStructuredLlm(NormalizingStructuredLlm):
    """适配 OpenAI-compatible Provider 的结构化 LLM 能力。"""

    def __init__(
        self,
        *,
        provider: LlmProviderName,
        provider_label: str,
        configuration: Settings = settings,
        client_factory: OpenAICompatibleClientFactory | None = None,
        chat_model: Any | None = None,
        normalizer: StructuredOutputNormalizer | None = None,
    ) -> None:
        raw_llm = OpenAICompatibleRawStructuredLlm(
            provider=provider,
            provider_label=provider_label,
            configuration=configuration,
            client_factory=client_factory,
            chat_model=chat_model,
        )
        super().__init__(
            raw_llm=raw_llm,
            normalizer=normalizer or SchemaAwareJsonStructuredOutputNormalizer(),
            provider_label=provider_label,
        )
        # 保留已有诊断和容器测试使用的 Provider 客户端观察入口。
        self._chat_model = raw_llm._chat_model
        self._client_factory = raw_llm._client_factory
        self.provider = provider
        self.model = raw_llm.model


class OpenAICompatibleRawStructuredLlm:
    """只负责发起 JSON Object 请求，不执行业务 Schema 校验。"""

    def __init__(
        self,
        *,
        provider: LlmProviderName,
        provider_label: str,
        configuration: Settings,
        client_factory: OpenAICompatibleClientFactory | None,
        chat_model: Any | None,
    ) -> None:
        self.provider = provider
        self.provider_label = provider_label
        self.provider_config = configuration.llm_provider_config(provider)
        self.model = self.provider_config.model or "unknown"
        self._chat_model = chat_model
        self._client_factory = client_factory

        if chat_model is not None:
            return
        if not self.provider_config.model:
            raise ServiceNotConfiguredError(
                f"未配置 {provider_label} Chat 模型，无法执行结构化 LLM 调用。"
            )
        if client_factory is None:
            raise RuntimeError(
                f"{provider_label} Structured Adapter 必须由 Composition Root 注入 Client Factory。"
            )
        self._chat_model = client_factory.create_chat_model(
            model=self.provider_config.model
        )

    def invoke_raw(
        self,
        request: StructuredLlmRequest,
        output_schema: type[BaseModel],
    ) -> RawStructuredLlmResponse:
        user_prompt = _append_schema_contract(request.user_prompt, output_schema)
        messages = [
            SystemMessage(content=request.system_prompt),
            HumanMessage(content=user_prompt),
        ]
        if self._client_factory is not None:
            response = self._invoke_json_object(messages)
        else:
            response = self._chat_model.bind(**self._bind_kwargs()).invoke(messages)
        return raw_response_from_provider_response(
            response,
            provider=self.provider,
            model=self.model,
        )

    def _bind_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {"response_format": {"type": "json_object"}}
        if self.provider_config.max_tokens is not None:
            kwargs["max_tokens"] = self.provider_config.max_tokens
        if self.provider_config.thinking is not None:
            kwargs["extra_body"] = {"thinking": {"type": self.provider_config.thinking}}
        return kwargs

    def _invoke_json_object(self, messages: list[object]) -> object:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": _openai_role(message.type), "content": message.content}
                for message in messages
            ],
            **self._bind_kwargs(),
            "temperature": self.provider_config.temperature,
        }
        if self.provider_config.max_tokens is not None:
            payload["max_tokens"] = self.provider_config.max_tokens
        return self._client_factory.create_client().chat.completions.create(**payload)


def _openai_role(message_type: str) -> str:
    return "user" if message_type == "human" else message_type


def _append_schema_contract(
    user_prompt: str, output_schema: type[BaseModel]
) -> str:
    schema_json = json.dumps(
        output_schema.model_json_schema(), ensure_ascii=False, separators=(",", ":")
    )
    return (
        f"{user_prompt}\n\n"
        "目标 JSON Schema（必须直接返回其 object 内容，不要使用额外包装键）：\n"
        f"{schema_json}"
    )
