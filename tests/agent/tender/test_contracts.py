from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.business.agents.tender.application.capabilities import (
    V1_GENERATE_SKELETON_CAPABILITY,
    V2_FILL_CONTENT_CAPABILITY_NAME,
    TenderCapabilityRegistry,
)
from app.business.agents.tender.contracts import (
    TenderAnalysis,
    TenderOutputPlan,
    TenderRequirement,
    TenderSourceEvidence,
)


def _single_analysis() -> TenderAnalysis:
    return TenderAnalysis(
        status="completed",
        package_type="single_volume",
        summary="招标文件要求提交一份投标文件。",
        key_requirements=[
            TenderRequirement(
                requirement_id="req-1",
                title="投标文件构成",
                kind="composition",
                evidence_refs=["ev-1"],
            )
        ],
        outputs=[
            TenderOutputPlan(
                name="投标文件",
                slug="bid",
                document_label="投标文件",
                requirement_refs=["req-1"],
                evidence_refs=["ev-1"],
            )
        ],
        evidence=[
            TenderSourceEvidence(
                evidence_id="ev-1",
                location="第六章/投标文件格式",
                quote="投标文件由以下文件组成",
            )
        ],
    )


def test_tender_analysis_validates_single_volume_contract() -> None:
    analysis = _single_analysis()

    assert analysis.package_type == "single_volume"
    assert analysis.outputs[0].evidence_refs == ["ev-1"]


def test_tender_analysis_requires_non_empty_evidence_fields() -> None:
    with pytest.raises(ValidationError):
        TenderSourceEvidence(evidence_id="", location="", quote="")


def test_tender_capability_registry_exposes_v1_without_v2() -> None:
    registry = TenderCapabilityRegistry([V1_GENERATE_SKELETON_CAPABILITY])

    assert [item.name for item in registry.list_available()] == [
        "tender.generate_bid_skeleton"
    ]
    with pytest.raises(KeyError, match="tender.fill_bid_content"):
        registry.get(V2_FILL_CONTENT_CAPABILITY_NAME)

