"""Run one small real Tender chunk call with redacted diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.composition.llm import build_structured_llm
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.modules.agent.tender.application.prompts import (
    TENDER_CHUNK_EXTRACT_PROMPT_VERSION,
    build_tender_chunk_request,
)
from app.modules.agent.tender.contracts import TenderChunk, TenderChunkAnalysis
from app.shared.config import settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("glm", "deepseek"), default=None)
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()
    provider = args.provider or settings.llm_provider
    updates: dict[str, object] = {"llm_provider": provider}
    if args.timeout is not None:
        timeout_field = (
            "deepseek_timeout_seconds"
            if provider == "deepseek"
            else "zhipu_timeout_seconds"
        )
        updates[timeout_field] = args.timeout
    configuration = settings.model_copy(update=updates)
    provider_config = configuration.llm_provider_config()
    result: dict[str, object] = {
        "provider": provider_config.provider,
        "model": provider_config.model or "",
        "response_format": "json_object",
        "scope": "single_chunk_provider_smoke_only",
        "prompt_version": TENDER_CHUNK_EXTRACT_PROMPT_VERSION,
        "max_tokens": provider_config.max_tokens,
        "input_chars": 0,
        "status": "not_run",
    }
    factory = OpenAICompatibleClientFactory(
        configuration=configuration,
        provider=provider,
    )
    try:
        llm = build_structured_llm(factory)
        chunk = TenderChunk(
            chunk_id="chunk-smoke-0001",
            sequence=1,
            text=(
                "[evidence_id=evidence-smoke-1] 招标文件要求提交一份投标文件，"
                "投标文件应包含投标函和资格证明材料。"
            ),
            evidence_ids=("evidence-smoke-1",),
            heading_path=("投标文件组成",),
            estimated_tokens=40,
        )
        request = build_tender_chunk_request(chunk=chunk)
        result["input_chars"] = len(request.user_prompt)
        started = perf_counter()
        response = llm.invoke(request, TenderChunkAnalysis)
        result.update(
            {
                "status": "ok",
                "duration_ms": round((perf_counter() - started) * 1000, 2),
                "output_chars": len(
                    json.dumps(response.value.model_dump(mode="json"), ensure_ascii=False)
                ),
                "finish_reason": response.finish_reason,
                "usage": response.usage,
            }
        )
        return_code = 0
    except Exception as exc:  # noqa: BLE001 - probe must classify provider failures
        result.update(
            {
                "status": "failed",
                "exception_type": f"{type(exc).__module__}.{type(exc).__name__}",
                "message": str(exc)[:300],
            }
        )
        return_code = 1
    finally:
        factory.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
