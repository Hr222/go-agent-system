"""Run a simple real Tender MVP with sequential chunk calls and DOCX output."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.composition.llm import build_structured_llm
from app.infrastructure.documents.tender_docx import TenderDocxReader, TenderDocxSkeletonRenderer
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.modules.agent.tender.application.chunking import TenderChunkPlanner
from app.modules.agent.tender.application.prompts import (
    build_tender_chunk_request,
    build_tender_merge_request,
)
from app.modules.agent.tender.contracts import (
    TenderAnalysis,
    TenderAnalysisBudget,
    TenderChunkAnalysis,
)
from app.shared.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--provider", choices=("glm", "deepseek"), default=None)
    parser.add_argument("--focus", default=None)
    parser.add_argument("--chunk-chars", type=int, default=8_000)
    parser.add_argument("--merge-items", type=int, default=4)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    provider = args.provider or settings.llm_provider
    configuration = settings.model_copy(update={"llm_provider": provider})
    output_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="tender-mvp-"))
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, object] = {
        "status": "failed",
        "scope": "simple_chunk_extract_merge",
        "source_name": args.source.name,
        "provider": provider,
        "output_dir": str(output_dir),
        "chunk_chars": args.chunk_chars,
        "merge_items": args.merge_items,
    }
    factory: OpenAICompatibleClientFactory | None = None

    try:
        content = args.source.read_bytes()
        reader = TenderDocxReader(
            max_bytes=configuration.tender_upload_max_size_bytes,
            hard_max_bytes=configuration.tender_hard_max_size_bytes,
            max_uncompressed_bytes=configuration.tender_max_uncompressed_bytes,
            max_zip_entries=configuration.tender_max_zip_entries,
            max_compression_ratio=configuration.tender_max_compression_ratio,
        )
        document = reader.read(file_name=args.source.name, content=content)
        budget = TenderAnalysisBudget(
            chunk_input_chars=args.chunk_chars,
            max_chunks=configuration.tender_max_chunks,
        )
        plan = TenderChunkPlanner().plan(document=document, budget=budget)
        factory = OpenAICompatibleClientFactory(
            configuration=configuration,
            provider=provider,
        )
        llm = build_structured_llm(factory)

        started = perf_counter()
        chunk_results: list[TenderChunkAnalysis] = []
        print(f"[mvp] chunks={len(plan.chunks)} provider={provider}", file=sys.stderr, flush=True)
        for chunk_index, chunk in enumerate(plan.chunks, start=1):
            print(
                f"[mvp] chunk {chunk_index}/{len(plan.chunks)} id={chunk.chunk_id} "
                f"chars={len(chunk.text)}",
                file=sys.stderr,
                flush=True,
            )
            request = build_tender_chunk_request(chunk=chunk, user_focus=args.focus)
            response = _invoke_with_retry(
                llm=llm,
                request=request,
                schema=TenderChunkAnalysis,
                retries=args.retries,
            )
            local = TenderChunkAnalysis.model_validate(response.value)
            _validate_chunk(local, set(chunk.evidence_ids))
            chunk_results.append(local)
            print(
                f"[mvp] chunk {chunk_index}/{len(plan.chunks)} ok",
                file=sys.stderr,
                flush=True,
            )

        merge_calls = 0
        current: list[TenderChunkAnalysis | TenderAnalysis] = list(chunk_results)
        while len(current) > 1:
            merged: list[TenderAnalysis] = []
            for batch_index in range(0, len(current), args.merge_items):
                batch = tuple(current[batch_index : batch_index + args.merge_items])
                print(
                    f"[mvp] merge level={merge_calls + 1} items={len(batch)}",
                    file=sys.stderr,
                    flush=True,
                )
                request = build_tender_merge_request(
                    items=batch,
                    batch_id=f"mvp-merge-{merge_calls + 1:03d}",
                )
                response = _invoke_with_retry(
                    llm=llm,
                    request=request,
                    schema=TenderAnalysis,
                    retries=args.retries,
                )
                merged.append(TenderAnalysis.model_validate(response.value))
                merge_calls += 1
                print(
                    f"[mvp] merge level={merge_calls} ok",
                    file=sys.stderr,
                    flush=True,
                )
            current = merged

        analysis = current[0]
        _validate_analysis(analysis, set(document.block_map()))
        artifacts = TenderDocxSkeletonRenderer().render(
            document=document,
            analysis=analysis,
        )
        artifact_records: list[dict[str, object]] = []
        for artifact in artifacts:
            file_name = Path(artifact.file_name).name
            (output_dir / file_name).write_bytes(artifact.content)
            artifact_records.append(
                {"file_name": file_name, "bytes": len(artifact.content)}
            )
        result.update(
            {
                "status": "ok",
                "model": configuration.llm_provider_config(provider).model,
                "prompt_versions": {
                    "chunk": request.prompt_version,
                    "merge": build_tender_merge_request(
                        items=(analysis,), batch_id="version-probe"
                    ).prompt_version,
                },
                "document_blocks": len(document.blocks),
                "chunk_count": len(plan.chunks),
                "merge_call_count": merge_calls,
                "elapsed_seconds": round(perf_counter() - started, 2),
                "package_type": analysis.package_type,
                "analysis_status": analysis.status,
                "output_count": len(analysis.outputs),
                "artifacts": artifact_records,
            }
        )
        return_code = 0
    except Exception as exc:  # noqa: BLE001 - CLI reports a bounded diagnostic
        result.update(
            {
                "exception_type": f"{type(exc).__module__}.{type(exc).__name__}",
                "message": str(exc)[:300],
            }
        )
        return_code = 1
    finally:
        if factory is not None:
            factory.close()

    (output_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return return_code


def _invoke_with_retry(*, llm, request, schema, retries: int):
    last_error: Exception | None = None
    for _ in range(retries + 1):
        try:
            return llm.invoke(request, schema)
        except Exception as exc:  # noqa: BLE001 - MVP retry boundary
            last_error = exc
            print(
                f"[mvp] call failed attempt={_ + 1}/{retries + 1} "
                f"exception={type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )
    assert last_error is not None
    raise last_error


def _validate_chunk(result: TenderChunkAnalysis, evidence_ids: set[str]) -> None:
    referenced = {item.evidence_id for item in result.evidence}
    referenced.update(ref for item in result.requirements for ref in item.evidence_refs)
    referenced.update(ref for item in result.output_candidates for ref in item.evidence_refs)
    missing = sorted(referenced - evidence_ids)
    if missing:
        raise ValueError(
            "chunk references unknown local evidence: " + ", ".join(missing[:10])
        )


def _validate_analysis(analysis: TenderAnalysis, evidence_ids: set[str]) -> None:
    referenced = {item.evidence_id for item in analysis.evidence}
    referenced.update(ref for output in analysis.outputs for ref in output.evidence_refs)
    referenced.update(
        ref for item in analysis.key_requirements for ref in item.evidence_refs
    )
    missing = sorted(referenced - evidence_ids)
    if missing:
        raise ValueError("analysis references unknown document evidence")
    if not analysis.evidence:
        raise ValueError("analysis contains no document evidence")


if __name__ == "__main__":
    raise SystemExit(main())
