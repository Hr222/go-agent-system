from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.platform.knowledge.retrieval.vector_search import VectorSearchStrategyName
from app.scripts.run_retrieval_baseline import (
    BenchmarkCaseResult,
    EvalCaseDefinition,
    StrategyCaseResult,
    build_comparison_summary,
    build_eval_set_summary,
    build_strategy_summary,
    load_eval_cases,
)


def make_strategy_case_result(
    *,
    strategy: VectorSearchStrategyName,
    elapsed_ms: float,
    hit_count: int,
    top1_document_match: bool,
    top1_section_match: bool,
    top3_section_match: bool,
) -> StrategyCaseResult:
    """构造最小策略结果，便于聚焦 benchmark 汇总逻辑。"""

    return StrategyCaseResult(
        strategy=strategy,
        pipeline_strategy=f"hybrid-vector-keyword/{strategy}",
        vector_trace_source=f"source-{strategy}",
        elapsed_ms=elapsed_ms,
        hit_count=hit_count,
        expected_document_rank=1 if top1_document_match else None,
        expected_section_rank=1 if top1_section_match else None,
        top1_document_match=top1_document_match,
        top1_section_match=top1_section_match,
        top3_section_match=top3_section_match,
        top_hits=[],
    )


def test_build_strategy_summary_aggregates_counts_and_latency() -> None:
    results = [
        BenchmarkCaseResult(
            case_id="case-1",
            query="问题一",
            expected_document_name="制度A",
            expected_section_title="第一条",
            strategy_results={
                "exact": make_strategy_case_result(
                    strategy="exact",
                    elapsed_ms=12.0,
                    hit_count=3,
                    top1_document_match=True,
                    top1_section_match=True,
                    top3_section_match=True,
                ),
                "hnsw": make_strategy_case_result(
                    strategy="hnsw",
                    elapsed_ms=8.0,
                    hit_count=3,
                    top1_document_match=True,
                    top1_section_match=True,
                    top3_section_match=True,
                ),
            },
        ),
        BenchmarkCaseResult(
            case_id="case-2",
            query="问题二",
            expected_document_name="制度B",
            expected_section_title="第二条",
            strategy_results={
                "exact": make_strategy_case_result(
                    strategy="exact",
                    elapsed_ms=18.0,
                    hit_count=0,
                    top1_document_match=False,
                    top1_section_match=False,
                    top3_section_match=False,
                ),
                "hnsw": make_strategy_case_result(
                    strategy="hnsw",
                    elapsed_ms=14.0,
                    hit_count=1,
                    top1_document_match=False,
                    top1_section_match=False,
                    top3_section_match=False,
                ),
            },
        ),
    ]

    summary = build_strategy_summary(results, "exact")

    assert summary == {
        "total_cases": 2,
        "top1_document_match_count": 1,
        "document_hit_at_3_count": 1,
        "top1_section_match_count": 1,
        "top3_section_match_count": 1,
        "zero_hit_count": 1,
        "average_hit_count": 1.5,
        "average_elapsed_ms": 15.0,
    }


def test_build_comparison_summary_marks_regression_and_speedup() -> None:
    results = [
        BenchmarkCaseResult(
            case_id="case-1",
            query="问题一",
            expected_document_name="制度A",
            expected_section_title="第一条",
            strategy_results={
                "exact": make_strategy_case_result(
                    strategy="exact",
                    elapsed_ms=12.0,
                    hit_count=3,
                    top1_document_match=True,
                    top1_section_match=True,
                    top3_section_match=True,
                ),
                "hnsw": make_strategy_case_result(
                    strategy="hnsw",
                    elapsed_ms=9.0,
                    hit_count=3,
                    top1_document_match=True,
                    top1_section_match=False,
                    top3_section_match=False,
                ),
            },
        ),
        BenchmarkCaseResult(
            case_id="case-2",
            query="问题二",
            expected_document_name="制度B",
            expected_section_title="第二条",
            strategy_results={
                "exact": make_strategy_case_result(
                    strategy="exact",
                    elapsed_ms=15.0,
                    hit_count=2,
                    top1_document_match=False,
                    top1_section_match=False,
                    top3_section_match=False,
                ),
                "hnsw": make_strategy_case_result(
                    strategy="hnsw",
                    elapsed_ms=18.0,
                    hit_count=3,
                    top1_document_match=True,
                    top1_section_match=True,
                    top3_section_match=True,
                ),
            },
        ),
    ]

    comparison = build_comparison_summary(results)

    assert comparison == {
        "compared_case_count": 2,
        "candidate_top1_document_better_count": 1,
        "candidate_top1_document_worse_count": 0,
        "candidate_top1_section_better_count": 1,
        "candidate_top1_section_worse_count": 1,
        "candidate_top3_section_better_count": 1,
        "candidate_top3_section_worse_count": 1,
        "candidate_faster_case_count": 1,
        "baseline_faster_case_count": 1,
        "same_latency_case_count": 0,
        "average_elapsed_delta_ms": 0.0,
        "top3_section_regression_case_ids": ["case-1"],
    }


def test_load_eval_cases_validates_required_fields_and_deduplicates_tags(
    tmp_path: Path,
) -> None:
    eval_path = tmp_path / "eval.json"
    eval_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "HR-001",
                    "query": "员工试用期多久",
                    "expected_document_name": "制度A",
                    "expected_section_title": "第五条",
                    "policy_category": "管理制度",
                    "question_type": "时效",
                    "tags": ["试用期", "录用", "试用期"],
                    "notes": "验证试用期条款是否能稳定命中。",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = load_eval_cases(eval_path)

    assert cases == [
        EvalCaseDefinition(
            case_id="HR-001",
            query="员工试用期多久",
            expected_document_name="制度A",
            expected_section_title="第五条",
            policy_category="管理制度",
            question_type="时效",
            tags=("试用期", "录用"),
            notes="验证试用期条款是否能稳定命中。",
        )
    ]


def test_load_eval_cases_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    eval_path = tmp_path / "eval.json"
    eval_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "HR-001",
                    "query": "问题一",
                    "expected_document_name": "制度A",
                    "expected_section_title": "第一条",
                    "policy_category": "管理制度",
                    "question_type": "定义",
                },
                {
                    "case_id": "HR-001",
                    "query": "问题二",
                    "expected_document_name": "制度A",
                    "expected_section_title": "第二条",
                    "policy_category": "管理制度",
                    "question_type": "条件",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="重复 case_id"):
        load_eval_cases(eval_path)


def test_build_eval_set_summary_counts_categories_question_types_and_tags() -> None:
    summary = build_eval_set_summary(
        [
            EvalCaseDefinition(
                case_id="HR-001",
                query="适用于哪些人",
                expected_document_name="人事管理制度",
                expected_section_title="第二条",
                policy_category="管理制度",
                question_type="适用范围",
                tags=("适用范围", "总则"),
            ),
            EvalCaseDefinition(
                case_id="HR-002",
                query="试用期多久",
                expected_document_name="人事管理制度",
                expected_section_title="第五条",
                policy_category="管理制度",
                question_type="时效",
                tags=("试用期", "录用"),
            ),
            EvalCaseDefinition(
                case_id="HR-003",
                query="出差回来要做什么",
                expected_document_name="人事管理制度",
                expected_section_title="第三十三条",
                policy_category="管理制度",
                question_type="流程",
                tags=("出差", "流程"),
            ),
        ]
    )

    assert summary == {
        "total_cases": 3,
        "distinct_document_count": 1,
        "policy_category_counts": {"管理制度": 3},
        "question_type_counts": {"时效": 1, "流程": 1, "适用范围": 1},
        "tag_counts": {
            "出差": 1,
            "总则": 1,
            "录用": 1,
            "流程": 1,
            "试用期": 1,
            "适用范围": 1,
        },
    }


def test_section_match_requires_expected_document_not_just_same_section_title() -> None:
    results = [
        BenchmarkCaseResult(
            case_id="case-1",
            query="适用于哪些人",
            expected_document_name="示例人事制度",
            expected_section_title="第二条",
            strategy_results={
                "exact": StrategyCaseResult(
                    strategy="exact",
                    pipeline_strategy="hybrid-vector-keyword/exact",
                    vector_trace_source="pgvector_cosine_exact",
                    elapsed_ms=12.0,
                    hit_count=3,
                    expected_document_rank=2,
                    expected_section_rank=None,
                    top1_document_match=False,
                    top1_section_match=False,
                    top3_section_match=False,
                    top_hits=[],
                )
            },
        )
    ]

    summary = build_strategy_summary(results, "exact")

    assert summary["top1_document_match_count"] == 0
    assert summary["document_hit_at_3_count"] == 1
    assert summary["top1_section_match_count"] == 0
    assert summary["top3_section_match_count"] == 0
