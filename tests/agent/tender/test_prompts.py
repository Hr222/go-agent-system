from app.business.agents.tender.application.prompts import (
    TENDER_BOUNDARY_VERIFY_PROMPT_VERSION,
    TENDER_CHUNK_EXTRACT_PROMPT_VERSION,
    TENDER_MERGE_PROMPT_VERSION,
    TENDER_SKELETON_PROMPT_VERSION,
    build_tender_boundary_verification_request,
    build_tender_chunk_request,
    build_tender_merge_request,
    build_tender_skeleton_request,
)
from app.business.agents.tender.contracts import TenderAnalysis, TenderChunk, TenderChunkAnalysis


def test_skeleton_prompt_requires_body_format_and_explicit_volume_boundaries() -> None:
    request = build_tender_skeleton_request(
        source_text="[evidence_id=ev-1] 第一部分 商务技术标\n[evidence_id=ev-2] 第二部分 经济标",
        user_focus="重点关注文件分线",
    )

    assert request.prompt_version == TENDER_SKELETON_PROMPT_VERSION
    assert "排除目录" in request.system_prompt
    assert "正文中同级标题切分" in request.system_prompt
    assert "前置章节中仅有要求" in request.system_prompt
    assert "V2" not in request.system_prompt
    assert "ev-1" in request.user_prompt
    assert "重点关注文件分线" in request.user_prompt


def test_skeleton_prompt_normalizes_empty_focus_without_inventing_context() -> None:
    request = build_tender_skeleton_request(
        source_text="[evidence_id=ev-1] 投标文件格式",
        user_focus="  ",
    )

    assert "无额外关注点" in request.user_prompt
    assert "公司知识库" in request.system_prompt


def test_boundary_verification_prompt_is_a_separate_structured_stage() -> None:
    request = build_tender_boundary_verification_request(
        boundary_context="[evidence_id=ev-1] 投标文件格式\n[evidence_id=ev-2] 投标函",
        proposed_start_block_id="ev-1",
        proposed_end_block_id="ev-2",
    )

    assert request.prompt_version == TENDER_BOUNDARY_VERIFY_PROMPT_VERSION
    assert "should_adjust" in request.system_prompt
    assert "ev-1" in request.user_prompt
    assert "ev-2" in request.user_prompt


def test_chunk_prompt_is_local_and_does_not_make_global_volume_decision() -> None:
    request = build_tender_chunk_request(
        chunk=TenderChunk(
            chunk_id="chunk-1",
            sequence=1,
            text="[evidence_id=ev-1] 第一部分 商务技术标",
            evidence_ids=("ev-1",),
            heading_path=("投标文件格式",),
        )
    )

    assert request.prompt_version == TENDER_CHUNK_EXTRACT_PROMPT_VERSION
    assert "只分析当前分块" in request.system_prompt
    assert "不做全局结论" in request.system_prompt
    assert "输出必须紧凑" in request.system_prompt
    assert "quote 只摘录不超过 120 个字符" in request.system_prompt
    assert (
        "kind 只能使用 composition、section、form、table、attachment、submission、"
        "placeholder 或 risk"
    ) in request.system_prompt
    assert "chunk-1" in request.user_prompt
    assert "ev-1" in request.user_prompt
    assert "当前分块允许引用的 evidence_id" in request.user_prompt


def test_merge_prompt_preserves_explicit_volume_order_and_rejects_toc_boundaries() -> None:
    request = build_tender_merge_request(
        items=(
            TenderChunkAnalysis(chunk_id="chunk-1"),
            TenderChunkAnalysis(chunk_id="chunk-2"),
        ),
        batch_id="merge-1",
    )

    assert request.prompt_version == TENDER_MERGE_PROMPT_VERSION
    assert "正文中明确的同级分卷标题" in request.system_prompt
    assert "目录" in request.system_prompt
    assert "V2" not in request.system_prompt
    assert "归并批次：merge-1" in request.user_prompt
    assert "删除重复证据和重复说明" in request.system_prompt
    assert "key_requirements 中的 kind 只能使用" in request.system_prompt


def test_merge_prompt_accepts_previous_tender_analysis() -> None:
    analysis = TenderAnalysis(
        status="completed",
        package_type="single_volume",
        summary="格式区骨架",
    )

    request = build_tender_merge_request(items=(analysis,), batch_id="merge-2")

    assert "格式区骨架" in request.user_prompt
