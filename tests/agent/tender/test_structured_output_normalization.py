from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError

from app.infrastructure.llm.structured_output_normalization import (
    NormalizingStructuredLlm,
    RawStructuredLlmResponse,
    SchemaAwareJsonStructuredOutputNormalizer,
    StructuredOutputNormalizerRegistry,
    build_default_normalizer_registry,
    raw_response_from_provider_response,
)
from app.modules.agent.tender.contracts import TenderAnalysis, TenderChunkAnalysis
from app.modules.llm.contracts import StructuredLlmRequest
from app.shared.exceptions import UpstreamServiceError


class ProbeResult(BaseModel):
    status: str
    message: str


def _raw(
    content: object,
    *,
    reasoning: object | None = None,
    finish_reason: str | None = None,
    usage: dict[str, object] | None = None,
) -> RawStructuredLlmResponse:
    return RawStructuredLlmResponse(
        provider="glm",
        model="glm-5",
        content=content,
        reasoning_content=reasoning,
        response_format="test",
        finish_reason=finish_reason,
        usage=usage,
    )


def test_schema_aware_normalizer_accepts_direct_json() -> None:
    result = SchemaAwareJsonStructuredOutputNormalizer().normalize(
        _raw({"status": "ok", "message": "direct"}), ProbeResult
    )

    assert result == ProbeResult(status="ok", message="direct")


def test_schema_aware_normalizer_unwraps_schema_named_json() -> None:
    result = SchemaAwareJsonStructuredOutputNormalizer().normalize(
        _raw({"probe_result": {"status": "ok", "message": "wrapped"}}),
        ProbeResult,
    )

    assert result.message == "wrapped"


def test_schema_aware_normalizer_unwraps_tender_chunk_and_tender_analysis() -> None:
    normalizer = SchemaAwareJsonStructuredOutputNormalizer()

    chunk = normalizer.normalize(
        _raw({"tender_chunk_analysis": {"chunk_id": "chunk-1"}}),
        TenderChunkAnalysis,
    )
    analysis = normalizer.normalize(
        _raw(
            {
                "tender_analysis": {
                    "status": "needs_review",
                    "package_type": "uncertain",
                    "summary": "待确认",
                }
            }
        ),
        TenderAnalysis,
    )

    assert chunk.chunk_id == "chunk-1"
    assert analysis.status == "needs_review"


def test_schema_aware_normalizer_removes_json_code_fence_and_ignores_reasoning() -> None:
    result = SchemaAwareJsonStructuredOutputNormalizer().normalize(
        _raw(
            '```json\n{"status":"ok","message":"business"}\n```',
            reasoning="这段思考不属于业务结果。",
        ),
        ProbeResult,
    )

    assert result.message == "business"


def test_schema_aware_normalizer_removes_explicit_thinking_block() -> None:
    result = SchemaAwareJsonStructuredOutputNormalizer().normalize(
        _raw('<think>内部推理</think>{"status":"ok","message":"done"}'),
        ProbeResult,
    )

    assert result.status == "ok"


def test_schema_aware_normalizer_rejects_unknown_wrapper_and_ambiguous_content() -> None:
    normalizer = SchemaAwareJsonStructuredOutputNormalizer()

    with pytest.raises(ValueError, match="包装"):
        normalizer.normalize(
            _raw({"unknown_result": {"status": "ok", "message": "x"}}),
            ProbeResult,
        )


def test_schema_aware_normalizer_rejects_wrapper_with_extra_top_level_fields() -> None:
    normalizer = SchemaAwareJsonStructuredOutputNormalizer()

    with pytest.raises(ValueError, match="额外顶层字段"):
        normalizer.normalize(
            _raw(
                {
                    "probe_result": {"status": "ok", "message": "wrapped"},
                    "metadata": {"source": "provider"},
                }
            ),
            ProbeResult,
        )
    with pytest.raises(ValueError, match="包装"):
        normalizer.normalize(
            _raw(
                {
                    "first": {"status": "ok"},
                    "second": {"message": "ambiguous"},
                }
            ),
            ProbeResult,
        )


def test_schema_aware_normalizer_rejects_invalid_json_and_field_type() -> None:
    normalizer = SchemaAwareJsonStructuredOutputNormalizer()

    with pytest.raises(ValueError, match="合法 JSON"):
        normalizer.normalize(_raw("not-json"), ProbeResult)
    with pytest.raises(ValidationError):
        normalizer.normalize(
            _raw({"status": "ok", "message": {"not": "a string"}}),
            ProbeResult,
        )


class _RawFake:
    def invoke_raw(
        self,
        request: StructuredLlmRequest,
        output_schema: type[BaseModel],
    ) -> RawStructuredLlmResponse:
        assert request.prompt_version == "normalization-test-v1"
        assert output_schema is ProbeResult
        return _raw(
            {"probe_result": {"status": "ok", "message": "decorated"}},
            finish_reason="stop",
            usage={"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
        )


def test_normalizing_structured_llm_preserves_existing_result_contract() -> None:
    adapter = NormalizingStructuredLlm(
        raw_llm=_RawFake(),
        normalizer=SchemaAwareJsonStructuredOutputNormalizer(),
        provider_label="GLM",
    )

    result = adapter.invoke(
        StructuredLlmRequest("system", "user", "normalization-test-v1"),
        ProbeResult,
    )

    assert result.value.message == "decorated"
    assert result.model == "glm-5"
    assert result.prompt_version == "normalization-test-v1"
    assert result.finish_reason == "stop"
    assert result.usage == {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17}


def test_normalizing_structured_llm_maps_normalization_failure_without_raw_content() -> None:
    class InvalidRaw:
        def invoke_raw(
            self,
            request: StructuredLlmRequest,
            output_schema: type[BaseModel],
        ) -> RawStructuredLlmResponse:
            del request
            del output_schema
            return _raw(json.dumps({"secret_raw_content": "do-not-leak"}))

    adapter = NormalizingStructuredLlm(
        raw_llm=InvalidRaw(),
        normalizer=SchemaAwareJsonStructuredOutputNormalizer(),
        provider_label="GLM",
    )

    with pytest.raises(UpstreamServiceError) as exc_info:
        adapter.invoke(StructuredLlmRequest("system", "user", "v1"), ProbeResult)

    assert "secret_raw_content" not in str(exc_info.value)


def test_normalizing_structured_llm_reports_length_finish_reason_without_raw_content() -> None:
    class TruncatedRaw:
        def invoke_raw(
            self,
            request: StructuredLlmRequest,
            output_schema: type[BaseModel],
        ) -> RawStructuredLlmResponse:
            del request, output_schema
            return RawStructuredLlmResponse(
                provider="glm",
                model="glm-5",
                content='{"status":"ok"',
                response_format="openai_chat_completion",
                finish_reason="length",
            )

    adapter = NormalizingStructuredLlm(
        raw_llm=TruncatedRaw(),
        normalizer=SchemaAwareJsonStructuredOutputNormalizer(),
        provider_label="GLM",
    )

    with pytest.raises(UpstreamServiceError, match="max_tokens"):
        adapter.invoke(StructuredLlmRequest("system", "user", "v1"), ProbeResult)


def test_raw_openai_response_preserves_finish_reason_and_usage() -> None:
    raw = raw_response_from_provider_response(
        {
            "choices": [
                {
                    "message": {"content": '{"status":"ok","message":"x"}'},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
        },
        provider="deepseek",
        model="deepseek-v4-flash",
    )

    assert raw.finish_reason == "stop"
    assert raw.usage == {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}


def test_normalizer_registry_supports_provider_and_model_extension_points() -> None:
    normalizer = SchemaAwareJsonStructuredOutputNormalizer()
    registry = StructuredOutputNormalizerRegistry()
    registry.register("future-provider", normalizer)
    registry.register("future-provider", normalizer, model="future-model")

    assert registry.resolve("future-provider") is normalizer
    assert registry.resolve("future-provider", model="future-model") is normalizer
    with pytest.raises(ValueError, match="未注册"):
        registry.resolve("missing-provider")


def test_default_registry_shares_schema_aware_normalizer_between_providers() -> None:
    registry = build_default_normalizer_registry()

    assert isinstance(
        registry.resolve("glm"), SchemaAwareJsonStructuredOutputNormalizer
    )
    assert registry.resolve("glm") is registry.resolve("deepseek")
