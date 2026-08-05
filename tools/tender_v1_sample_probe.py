"""Run the V1 document and renderer probe over the external demo corpus.

This probe deliberately uses a deterministic analysis fixture. It verifies DOCX
intake, evidence addressing, single/multi artifact rendering, and output files
without pretending that a model response has semantically reviewed the corpus.
"""

from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docx import Document

from app.infrastructure.documents.tender_docx import TenderDocxReader, TenderDocxSkeletonRenderer
from app.modules.agent.tender.application.service import TenderApplication
from app.modules.agent.tender.contracts import (
    TenderAnalysis,
    TenderAnalysisBudget,
    TenderChunkAnalysis,
    TenderChunkOutputCandidate,
    TenderGenerateSkeletonCommand,
    TenderOutputPlan,
    TenderSourceEvidence,
)
from app.modules.llm.contracts import StructuredLlmResult


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo-root",
        type=Path,
        default=Path(r"D:\workspace\bid-tech-generator\demo"),
    )
    args = parser.parse_args()
    samples = _select_samples(args.demo_root)
    reader = TenderDocxReader(
        max_bytes=50 * 1024 * 1024,
        hard_max_bytes=70 * 1024 * 1024,
    )
    renderer = TenderDocxSkeletonRenderer()
    records: list[dict[str, object]] = []

    for package_type, source_path in samples:
        try:
            document = reader.read(file_name=source_path.name, content=source_path.read_bytes())
            fake_llm = _ProbeLlm(
                package_type=package_type,
                evidence_id=document.blocks[0].block_id,
            )
            application = TenderApplication(
                llm=fake_llm,
                chunk_llm=fake_llm,
                merge_llm=fake_llm,
                reader=_FixedReader(document),
                renderer=renderer,
                budget=TenderAnalysisBudget(
                    chunk_input_chars=8_000,
                    max_merge_items=8,
                    max_chunks=128,
                ),
            )
            result = application.execute(
                TenderGenerateSkeletonCommand(file_name=source_path.name, content=b"probe")
            )
            for artifact in result.artifacts:
                Document(BytesIO(artifact.content))
            records.append(
                {
                    "package_type": package_type,
                    "sample": source_path.parent.name,
                    "source_file": str(source_path),
                    "status": "structural_pass_semantic_unverified",
                    "expected_artifacts": len(result.analysis.outputs),
                    "actual_artifacts": len(result.artifacts),
                    "docx_opened": True,
                    "chunk_count": fake_llm.chunk_calls,
                    "merge_call_count": fake_llm.merge_calls,
                    "evidence_coverage": len(document.blocks),
                    "semantic_verification": "deterministic_fake_llm_only",
                }
            )
        except Exception as exc:  # noqa: BLE001 - one sample must not hide others
            records.append(
                {
                    "package_type": package_type,
                    "sample": source_path.parent.name,
                    "source_file": str(source_path),
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "semantic_verification": "deterministic_fake_llm_only",
                }
            )

    print(json.dumps(records, ensure_ascii=False, indent=2))


def _select_samples(demo_root: Path) -> list[tuple[str, Path]]:
    samples: list[tuple[str, Path]] = []
    category_counts = {
        "01_double_toc": 2,
        "02_mostly_correct": 2,
        "03_appendix_missing": 2,
        "04_front_capture": 2,
        "05_boundary_bleed": 1,
        "06_structure_failure": 1,
    }
    for category, count in category_counts.items():
        category_root = demo_root / "single" / category
        for sample_root in sorted(
            p
            for p in category_root.iterdir()
            if p.is_dir() and not p.name.startswith("_skill_test")
        )[:count]:
            source = _source_docx(sample_root)
            if source is not None:
                samples.append(("single_volume", source))

    multi_roots = [
        p for p in sorted((demo_root / "multi").iterdir())
        if p.is_dir() and not p.name.startswith("_skill_test")
    ]
    for sample_root in multi_roots[:10]:
        source = _source_docx(sample_root)
        if source is not None:
            samples.append(("multi_volume", source))
    return samples


def _source_docx(sample_root: Path) -> Path | None:
    candidates = sorted(
        path for path in sample_root.rglob("*.docx")
        if "_skill_output" not in path.parts
        and not path.name.startswith("~$")
        and path.name not in {"投标文件.docx", "响应文件.docx"}
    )
    return candidates[0] if candidates else None


class _FixedReader:
    def __init__(self, document):
        self.document = document

    def read(self, *, file_name: str, content: bytes):
        del file_name, content
        return self.document


class _ProbeLlm:
    def __init__(self, *, package_type: str, evidence_id: str) -> None:
        self.package_type = package_type
        self.evidence_id = evidence_id
        self.chunk_calls = 0
        self.merge_calls = 0

    def invoke(self, request, output_schema):
        if output_schema is TenderChunkAnalysis:
            self.chunk_calls += 1
            chunk_id = request.user_prompt.split("分块 ID：", 1)[1].split("\n", 1)[0]
            chunk_evidence_id = request.user_prompt.split("[evidence_id=", 1)[1].split("]", 1)[0]
            return StructuredLlmResult(
                value=TenderChunkAnalysis(
                    chunk_id=chunk_id,
                    output_candidates=[
                        TenderChunkOutputCandidate(
                            label="probe", evidence_refs=[chunk_evidence_id]
                        )
                    ],
                ),
                model="deterministic-probe",
                prompt_version=request.prompt_version,
            )
        self.merge_calls += 1
        outputs = [
            TenderOutputPlan(
                name=f"V1 probe {index}",
                slug=f"probe-{index}",
                document_label=f"probe output {index}",
                section_titles=("招标要求", "待填写内容"),
                evidence_refs=(self.evidence_id,),
            )
            for index in range(1, 2 if self.package_type == "single_volume" else 3)
        ]
        return StructuredLlmResult(
            value=TenderAnalysis(
                status="completed",
                package_type=self.package_type,
                summary="deterministic chunked structural probe",
                outputs=outputs,
                evidence=[
                    TenderSourceEvidence(
                        evidence_id=self.evidence_id,
                        location=self.evidence_id,
                        quote="source evidence",
                    )
                ],
            ),
            model="deterministic-probe",
            prompt_version=request.prompt_version,
        )


if __name__ == "__main__":
    main()
