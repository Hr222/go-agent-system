from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Mapping, Protocol

from pydantic import BaseModel

from app.platform.llm.contracts import (
    StructuredLlmPort,
    StructuredLlmRequest,
    StructuredLlmResult,
)
from app.shared.exceptions import UpstreamServiceError
from app.shared.logging import get_logger

logger = get_logger("app.infrastructure.llm.structured_output")


@dataclass(frozen=True, slots=True)
class RawStructuredLlmResponse:
    """Provider 原始结构化响应的安全内部表示。"""

    provider: str
    model: str
    content: object
    reasoning_content: object | None = None
    response_format: str = "unknown"
    finish_reason: str | None = None
    usage: Mapping[str, object] | None = None


class StructuredLlmRawPort(Protocol):
    """只负责调用 Provider 并返回未经业务 Schema 校验的响应。"""

    def invoke_raw(
        self,
        request: StructuredLlmRequest,
        output_schema: type[BaseModel],
    ) -> RawStructuredLlmResponse: ...


class StructuredOutputNormalizer(Protocol):
    """把原始结构化响应转换为目标结构化模型。"""

    def normalize(
        self,
        response: RawStructuredLlmResponse,
        output_schema: type[BaseModel],
    ) -> BaseModel: ...


class StructuredOutputNormalizerRegistry:
    """按 Provider 或 Provider/模型选择归一化器。"""

    def __init__(
        self,
        normalizers: Mapping[str, StructuredOutputNormalizer] | None = None,
    ) -> None:
        self._normalizers = dict(normalizers or {})

    def register(
        self,
        provider: str,
        normalizer: StructuredOutputNormalizer,
        *,
        model: str | None = None,
    ) -> None:
        key = _normalizer_key(provider, model)
        self._normalizers[key] = normalizer

    def resolve(
        self, provider: str, *, model: str | None = None
    ) -> StructuredOutputNormalizer:
        for key in (_normalizer_key(provider, model), _normalizer_key(provider, None)):
            normalizer = self._normalizers.get(key)
            if normalizer is not None:
                return normalizer
        raise ValueError(f"未注册 Provider 输出归一化器：{provider}/{model or 'default'}")


class NormalizingStructuredLlm(StructuredLlmPort):
    """在原始 Provider Port 和业务 Structured LLM Port 之间提供装饰层。"""

    def __init__(
        self,
        *,
        raw_llm: StructuredLlmRawPort,
        normalizer: StructuredOutputNormalizer,
        provider_label: str,
    ) -> None:
        self._raw_llm = raw_llm
        self._normalizer = normalizer
        self._provider_label = provider_label

    def invoke(
        self,
        request: StructuredLlmRequest,
        output_schema: type[BaseModel],
    ) -> StructuredLlmResult[BaseModel]:
        started = _monotonic()
        raw: RawStructuredLlmResponse | None = None
        try:
            raw = self._raw_llm.invoke_raw(request, output_schema)
            value = self._normalizer.normalize(raw, output_schema)
        except Exception as exc:  # noqa: BLE001 - Port 边界统一转换
            duration_ms = (_monotonic() - started) * 1000
            truncated = bool(raw and raw.finish_reason == "length")
            logger.error(
                "structured output normalization failed provider=%s model=%s "
                "schema=%s format=%s finish_reason=%s duration_ms=%.2f "
                "exception_type=%s",
                raw.provider if raw else self._provider_label,
                raw.model if raw else "unknown",
                output_schema.__name__,
                raw.response_format if raw else "raw_call_failed",
                raw.finish_reason if raw else None,
                duration_ms,
                type(exc).__name__,
            )
            if truncated:
                raise UpstreamServiceError(
                    f"{self._provider_label} 结构化调用失败（Prompt 版本："
                    f"{request.prompt_version}）：输出达到 max_tokens 上限，JSON 可能被截断"
                ) from exc
            raise UpstreamServiceError(
                f"{self._provider_label} 结构化调用失败（Prompt 版本：{request.prompt_version}）："
                f"{type(exc).__name__}"
            ) from exc

        logger.info(
            "structured output normalization success provider=%s model=%s "
            "schema=%s format=%s duration_ms=%.2f",
            raw.provider,
            raw.model,
            output_schema.__name__,
            raw.response_format,
            (_monotonic() - started) * 1000,
        )
        return StructuredLlmResult(
            value=value,
            model=raw.model,
            prompt_version=request.prompt_version,
            finish_reason=raw.finish_reason,
            usage=raw.usage,
        )


class SchemaAwareJsonStructuredOutputNormalizer:
    """归一化 Schema 感知的 JSON object、代码块和包装。"""

    def normalize(
        self,
        response: RawStructuredLlmResponse,
        output_schema: type[BaseModel],
    ) -> BaseModel:
        data = _parse_json_object(response.content)
        wrapper_keys = _schema_wrapper_keys(output_schema)
        matching_keys = [key for key in wrapper_keys if key in data]
        if len(matching_keys) > 1:
            raise ValueError("响应包含多个目标 Schema 包装对象")
        if matching_keys:
            wrapper_key = matching_keys[0]
            if len(data) != 1:
                raise ValueError("Schema 包装对象包含额外顶层字段")
            wrapped = data[wrapper_key]
            if not isinstance(wrapped, dict):
                raise ValueError(f"Schema 包装字段不是 JSON object：{wrapper_key}")
            data = wrapped
        elif _looks_like_unknown_wrapper(data, output_schema):
            raise ValueError("响应包含无法依据目标 Schema 确定的包装对象")
        return output_schema.model_validate(data)


def build_default_normalizer_registry() -> StructuredOutputNormalizerRegistry:
    """构造当前支持的 Provider 归一化器注册表。"""

    registry = StructuredOutputNormalizerRegistry()
    normalizer = SchemaAwareJsonStructuredOutputNormalizer()
    registry.register("glm", normalizer)
    registry.register("deepseek", normalizer)
    return registry


def raw_response_from_provider_response(
    response: object, *, provider: str, model: str
) -> RawStructuredLlmResponse:
    """从 OpenAI-compatible 或 LangChain 响应提取业务内容和思考字段。"""

    if isinstance(response, RawStructuredLlmResponse):
        return response

    if isinstance(response, dict) and isinstance(response.get("choices"), list):
        choice = response["choices"][0] if response["choices"] else {}
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        return RawStructuredLlmResponse(
            provider=provider,
            model=model,
            content=message.get("content") if isinstance(message, dict) else None,
            reasoning_content=(
                message.get("reasoning_content") if isinstance(message, dict) else None
            ),
            response_format="openai_chat_completion",
            finish_reason=(
                choice.get("finish_reason") if isinstance(choice, dict) else None
            ),
            usage=_usage_mapping(response.get("usage")),
        )

    if isinstance(response, dict):
        return RawStructuredLlmResponse(
            provider=provider,
            model=model,
            content=response.get("content", response),
            reasoning_content=response.get("reasoning_content"),
            response_format="json_object",
            finish_reason=_optional_string(response.get("finish_reason")),
            usage=_usage_mapping(response.get("usage")),
        )

    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        return RawStructuredLlmResponse(
            provider=provider,
            model=model,
            content=getattr(message, "content", None),
            reasoning_content=getattr(message, "reasoning_content", None),
            response_format="openai_chat_completion",
            finish_reason=_optional_string(getattr(choices[0], "finish_reason", None)),
            usage=_usage_mapping(getattr(response, "usage", None)),
        )

    return RawStructuredLlmResponse(
        provider=provider,
        model=model,
        content=getattr(response, "content", response),
        reasoning_content=getattr(response, "reasoning_content", None),
        response_format="langchain_content",
        finish_reason=_optional_string(getattr(response, "finish_reason", None)),
        usage=_usage_mapping(getattr(response, "usage_metadata", None))
        or _usage_mapping(getattr(response, "response_metadata", None)),
    )


def _usage_mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return None
    values: dict[str, object] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        item = getattr(value, key, None)
        if item is not None:
            values[key] = item
    return values or None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _parse_json_object(content: object) -> dict[str, object]:
    if isinstance(content, dict):
        return dict(content)
    if isinstance(content, list):
        content = _join_text_parts(content)
    if not isinstance(content, str):
        raise TypeError(f"结构化响应内容不是 JSON object：{type(content).__name__}")

    text = _remove_explicit_thinking_block(content).strip()
    text = _remove_json_code_fence(text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("结构化响应不是合法 JSON object") from exc
    if not isinstance(parsed, dict):
        raise TypeError("结构化响应必须是 JSON object")
    return parsed


def _remove_explicit_thinking_block(content: str) -> str:
    lowered = content.lower()
    start = lowered.find("<think>")
    if start < 0:
        return content
    end = lowered.find("</think>", start + len("<think>"))
    if end < 0:
        raise ValueError("思考标签未闭合")
    return content[:start] + content[end + len("</think>") :]


def _remove_json_code_fence(content: str) -> str:
    match = re.fullmatch(
        r"\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    if "```" in content:
        raise ValueError("结构化响应包含无法识别的 Markdown 代码块")
    return content


def _join_text_parts(parts: list[object]) -> str:
    texts: list[str] = []
    for part in parts:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])
        else:
            raise TypeError("结构化响应包含无法识别的内容片段")
    return "".join(texts)


def _schema_wrapper_keys(output_schema: type[BaseModel]) -> tuple[str, ...]:
    name = output_schema.__name__
    snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return snake_name, name


def _looks_like_unknown_wrapper(
    data: dict[str, object], output_schema: type[BaseModel]
) -> bool:
    fields = set(output_schema.model_fields)
    if not data or fields.intersection(data):
        return False
    return all(isinstance(value, dict) for value in data.values())


def _normalizer_key(provider: str, model: str | None) -> str:
    return f"{provider.lower()}:{model}" if model else provider.lower()


def _monotonic() -> float:
    from time import perf_counter

    return perf_counter()
