from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

from app.composition.knowledge import build_benchmark_retrieval_service
from app.platform.knowledge.ports.read_port import KnowledgeQuery, KnowledgeQueryTrace
from app.platform.knowledge.retrieval import KnowledgeRetrievalService
from app.platform.knowledge.retrieval.vector_search import (
    VectorSearchStrategyName,
)

DEFAULT_BENCHMARK_STRATEGIES: tuple[VectorSearchStrategyName, ...] = ("exact", "hnsw")


@dataclass(slots=True, frozen=True)
class EvalCaseDefinition:
    """定义单条检索评测样本。"""

    case_id: str
    query: str
    expected_document_name: str
    expected_section_title: str
    policy_category: str
    question_type: str
    tags: tuple[str, ...] = ()
    notes: str | None = None


@dataclass(slots=True)
class BaselineHitSummary:
    """记录单条命中结果的最小摘要，便于后续人工复核。"""

    rank: int
    policy_name: str
    section_title: str | None
    section_path: str | None
    score: float
    chunk_text_preview: str


@dataclass(slots=True)
class StrategyCaseResult:
    """记录单个策略在某个评测问题上的结果。"""

    strategy: VectorSearchStrategyName
    pipeline_strategy: str
    vector_trace_source: str | None
    elapsed_ms: float
    hit_count: int
    expected_document_rank: int | None
    expected_section_rank: int | None
    top1_document_match: bool
    top1_section_match: bool
    top3_section_match: bool
    top_hits: list[BaselineHitSummary]


@dataclass(slots=True)
class BenchmarkCaseResult:
    """记录单个评测问题在多种检索策略下的对比结果。"""

    case_id: str
    query: str
    expected_document_name: str
    expected_section_title: str
    strategy_results: dict[VectorSearchStrategyName, StrategyCaseResult]
    policy_category: str = "未分类"
    question_type: str = "未分类"
    tags: tuple[str, ...] = ()
    notes: str | None = None


def parse_args() -> argparse.Namespace:
    """解析 baseline / benchmark 脚本参数。"""

    parser = argparse.ArgumentParser(
        description="执行检索 baseline/benchmark，对比 exact 与 hnsw 两种向量召回策略。"
    )
    parser.add_argument(
        "--eval-set",
        default="tests/knowledge/fixtures/retrieval_eval_set_step_a.json",
        help="评测集文件路径，默认复用当前最小评测集。",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="每个问题返回的命中数量上限，默认 5。",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=DEFAULT_BENCHMARK_STRATEGIES,
        default=list(DEFAULT_BENCHMARK_STRATEGIES),
        help="需要对比的向量召回策略，默认同时跑 exact 与 hnsw。",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="可选：将 JSON 结果按 UTF-8 落盘到指定文件，避免终端重定向带来的编码问题。",
    )
    return parser.parse_args()


def load_eval_cases(eval_path: Path) -> list[EvalCaseDefinition]:
    """读取并校验检索评测集定义。"""

    payload = json.loads(eval_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("评测集文件必须是 JSON 数组。")

    cases: list[EvalCaseDefinition] = []
    seen_case_ids: set[str] = set()
    for index, raw_case in enumerate(payload, start=1):
        if not isinstance(raw_case, dict):
            raise ValueError(f"第 {index} 条评测样本必须是对象。")

        def read_required_text(field_name: str) -> str:
            value = raw_case.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"第 {index} 条评测样本缺少有效字段：{field_name}")
            return value.strip()

        case_id = read_required_text("case_id")
        if case_id in seen_case_ids:
            raise ValueError(f"评测集存在重复 case_id：{case_id}")
        seen_case_ids.add(case_id)

        raw_tags = raw_case.get("tags", [])
        if raw_tags is None:
            raw_tags = []
        if not isinstance(raw_tags, list):
            raise ValueError(f"第 {index} 条评测样本的 tags 必须是字符串数组。")

        tags: list[str] = []
        seen_tags: set[str] = set()
        for raw_tag in raw_tags:
            if not isinstance(raw_tag, str) or not raw_tag.strip():
                raise ValueError(f"第 {index} 条评测样本的 tags 必须是非空字符串。")
            normalized_tag = raw_tag.strip()
            if normalized_tag not in seen_tags:
                tags.append(normalized_tag)
                seen_tags.add(normalized_tag)

        raw_notes = raw_case.get("notes")
        if raw_notes is not None and (not isinstance(raw_notes, str) or not raw_notes.strip()):
            raise ValueError(f"第 {index} 条评测样本的 notes 如果提供，必须是非空字符串。")

        cases.append(
            EvalCaseDefinition(
                case_id=case_id,
                query=read_required_text("query"),
                expected_document_name=read_required_text("expected_document_name"),
                expected_section_title=read_required_text("expected_section_title"),
                policy_category=read_required_text("policy_category"),
                question_type=read_required_text("question_type"),
                tags=tuple(tags),
                notes=raw_notes.strip() if isinstance(raw_notes, str) else None,
            )
        )

    return cases


def build_retrieval_service(
    strategy_name: VectorSearchStrategyName,
) -> tuple[object, KnowledgeRetrievalService]:
    """通过 Composition Root 为指定策略构造独立检索服务。"""

    return build_benchmark_retrieval_service(strategy_name)


def extract_vector_trace(
    stages: tuple[KnowledgeQueryTrace, ...],
) -> KnowledgeQueryTrace | None:
    """提取向量召回阶段的调试信息，便于确认实际走到的策略。"""

    return next((stage for stage in stages if stage.name == "vector_recall"), None)


def normalize_policy_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = re.sub(r"^\d+[、，,\.\s]+", "", value.strip())
    return re.sub(r"\s+", "", normalized)


def normalize_section_label(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", "", value.strip())


def is_same_document(actual_name: str | None, expected_name: str) -> bool:
    return normalize_policy_name(actual_name) == normalize_policy_name(expected_name)


def is_same_section(
    *,
    actual_document_name: str | None,
    actual_section_title: str | None,
    expected_document_name: str,
    expected_section_title: str,
) -> bool:
    return is_same_document(actual_document_name, expected_document_name) and (
        normalize_section_label(actual_section_title)
        == normalize_section_label(expected_section_title)
    )


def run_single_case(
    *,
    service: KnowledgeRetrievalService,
    strategy_name: VectorSearchStrategyName,
    case: EvalCaseDefinition,
    top_k: int,
) -> StrategyCaseResult:
    """执行单个评测问题，并输出指定策略的最小对比结果。"""

    started_at = perf_counter()
    response = service.search(
        KnowledgeQuery(
            query=case.query,
            top_k=top_k,
        )
    )
    elapsed_ms = round((perf_counter() - started_at) * 1000, 3)

    top_hits = [
        BaselineHitSummary(
            rank=hit.rank,
            policy_name=hit.policy_name,
            section_title=hit.section_title,
            section_path=hit.section_path,
            score=hit.score,
            chunk_text_preview=hit.chunk_text[:120],
        )
        for hit in response.hits[:3]
    ]
    top1 = response.hits[0] if response.hits else None
    top3 = response.hits[:3]
    vector_trace = extract_vector_trace(response.traces)
    expected_document_rank = next(
        (
            hit.rank
            for hit in response.hits
            if is_same_document(hit.policy_name, case.expected_document_name)
        ),
        None,
    )
    expected_section_rank = next(
        (
            hit.rank
            for hit in response.hits
            if is_same_section(
                actual_document_name=hit.policy_name,
                actual_section_title=hit.section_title,
                expected_document_name=case.expected_document_name,
                expected_section_title=case.expected_section_title,
            )
        ),
        None,
    )

    return StrategyCaseResult(
        strategy=strategy_name,
        pipeline_strategy=response.strategy,
        vector_trace_source=vector_trace.source if vector_trace else None,
        elapsed_ms=elapsed_ms,
        hit_count=len(response.hits),
        expected_document_rank=expected_document_rank,
        expected_section_rank=expected_section_rank,
        top1_document_match=(
            top1 is not None and is_same_document(top1.policy_name, case.expected_document_name)
        ),
        top1_section_match=(
            top1 is not None
            and is_same_section(
                actual_document_name=top1.policy_name,
                actual_section_title=top1.section_title,
                expected_document_name=case.expected_document_name,
                expected_section_title=case.expected_section_title,
            )
        ),
        top3_section_match=any(
            is_same_section(
                actual_document_name=hit.policy_name,
                actual_section_title=hit.section_title,
                expected_document_name=case.expected_document_name,
                expected_section_title=case.expected_section_title,
            )
            for hit in top3
        ),
        top_hits=top_hits,
    )


def run_benchmark(
    eval_cases: list[EvalCaseDefinition],
    *,
    strategies: list[VectorSearchStrategyName],
    top_k: int,
) -> list[BenchmarkCaseResult]:
    """基于当前检索链路执行 exact / hnsw 对比 benchmark。"""

    services: dict[VectorSearchStrategyName, KnowledgeRetrievalService] = {}
    sessions: dict[VectorSearchStrategyName, object] = {}

    try:
        for strategy_name in strategies:
            session, service = build_retrieval_service(strategy_name)
            sessions[strategy_name] = session
            services[strategy_name] = service

        results: list[BenchmarkCaseResult] = []
        for case in eval_cases:
            strategy_results: dict[VectorSearchStrategyName, StrategyCaseResult] = {}
            for strategy_name in strategies:
                strategy_results[strategy_name] = run_single_case(
                    service=services[strategy_name],
                    strategy_name=strategy_name,
                    case=case,
                    top_k=top_k,
                )
                # HNSW 会在事务内设置查询参数，这里主动回滚，避免影响后续用例。
                sessions[strategy_name].rollback()

            results.append(
                BenchmarkCaseResult(
                    case_id=case.case_id,
                    query=case.query,
                    expected_document_name=case.expected_document_name,
                    expected_section_title=case.expected_section_title,
                    policy_category=case.policy_category,
                    question_type=case.question_type,
                    tags=case.tags,
                    notes=case.notes,
                    strategy_results=strategy_results,
                )
            )

        return results
    finally:
        for session in sessions.values():
            session.close()


def build_strategy_summary(
    results: list[BenchmarkCaseResult],
    strategy_name: VectorSearchStrategyName,
) -> dict[str, int | float]:
    """汇总单个策略的命中效果与耗时指标。"""

    strategy_results = [item.strategy_results[strategy_name] for item in results]
    total = len(strategy_results)
    if total == 0:
        return {
            "total_cases": 0,
            "top1_document_match_count": 0,
            "document_hit_at_3_count": 0,
            "top1_section_match_count": 0,
            "top3_section_match_count": 0,
            "zero_hit_count": 0,
            "average_hit_count": 0.0,
            "average_elapsed_ms": 0.0,
        }

    return {
        "total_cases": total,
        "top1_document_match_count": sum(item.top1_document_match for item in strategy_results),
        "document_hit_at_3_count": sum(
            item.expected_document_rank is not None and item.expected_document_rank <= 3
            for item in strategy_results
        ),
        "top1_section_match_count": sum(item.top1_section_match for item in strategy_results),
        "top3_section_match_count": sum(item.top3_section_match for item in strategy_results),
        "zero_hit_count": sum(item.hit_count == 0 for item in strategy_results),
        "average_hit_count": round(
            sum(item.hit_count for item in strategy_results) / total,
            3,
        ),
        "average_elapsed_ms": round(
            sum(item.elapsed_ms for item in strategy_results) / total,
            3,
        ),
    }


def build_comparison_summary(
    results: list[BenchmarkCaseResult],
    *,
    baseline_strategy: VectorSearchStrategyName = "exact",
    candidate_strategy: VectorSearchStrategyName = "hnsw",
) -> dict[str, int | float | list[str]]:
    """汇总候选策略相对 baseline 的收益、退化与耗时变化。"""

    if not results:
        return {
            "compared_case_count": 0,
            "candidate_top1_document_better_count": 0,
            "candidate_top1_document_worse_count": 0,
            "candidate_top1_section_better_count": 0,
            "candidate_top1_section_worse_count": 0,
            "candidate_top3_section_better_count": 0,
            "candidate_top3_section_worse_count": 0,
            "candidate_faster_case_count": 0,
            "baseline_faster_case_count": 0,
            "same_latency_case_count": 0,
            "average_elapsed_delta_ms": 0.0,
            "top3_section_regression_case_ids": [],
        }

    candidate_top1_document_better_count = 0
    candidate_top1_document_worse_count = 0
    candidate_top1_section_better_count = 0
    candidate_top1_section_worse_count = 0
    candidate_top3_section_better_count = 0
    candidate_top3_section_worse_count = 0
    candidate_faster_case_count = 0
    baseline_faster_case_count = 0
    same_latency_case_count = 0
    total_elapsed_delta = 0.0
    top3_section_regression_case_ids: list[str] = []

    for item in results:
        baseline_result = item.strategy_results[baseline_strategy]
        candidate_result = item.strategy_results[candidate_strategy]

        if candidate_result.top1_document_match and not baseline_result.top1_document_match:
            candidate_top1_document_better_count += 1
        if baseline_result.top1_document_match and not candidate_result.top1_document_match:
            candidate_top1_document_worse_count += 1

        if candidate_result.top1_section_match and not baseline_result.top1_section_match:
            candidate_top1_section_better_count += 1
        if baseline_result.top1_section_match and not candidate_result.top1_section_match:
            candidate_top1_section_worse_count += 1

        if candidate_result.top3_section_match and not baseline_result.top3_section_match:
            candidate_top3_section_better_count += 1
        if baseline_result.top3_section_match and not candidate_result.top3_section_match:
            candidate_top3_section_worse_count += 1
            top3_section_regression_case_ids.append(item.case_id)

        elapsed_delta = round(candidate_result.elapsed_ms - baseline_result.elapsed_ms, 3)
        total_elapsed_delta += elapsed_delta
        if elapsed_delta < 0:
            candidate_faster_case_count += 1
        elif elapsed_delta > 0:
            baseline_faster_case_count += 1
        else:
            same_latency_case_count += 1

    return {
        "compared_case_count": len(results),
        "candidate_top1_document_better_count": candidate_top1_document_better_count,
        "candidate_top1_document_worse_count": candidate_top1_document_worse_count,
        "candidate_top1_section_better_count": candidate_top1_section_better_count,
        "candidate_top1_section_worse_count": candidate_top1_section_worse_count,
        "candidate_top3_section_better_count": candidate_top3_section_better_count,
        "candidate_top3_section_worse_count": candidate_top3_section_worse_count,
        "candidate_faster_case_count": candidate_faster_case_count,
        "baseline_faster_case_count": baseline_faster_case_count,
        "same_latency_case_count": same_latency_case_count,
        "average_elapsed_delta_ms": round(total_elapsed_delta / len(results), 3),
        "top3_section_regression_case_ids": top3_section_regression_case_ids,
    }


def build_eval_set_summary(
    eval_cases: list[EvalCaseDefinition],
) -> dict[str, int | dict[str, int]]:
    """汇总评测集覆盖面，便于观察样本是否仍然过于集中。"""

    policy_category_counts = Counter(case.policy_category for case in eval_cases)
    question_type_counts = Counter(case.question_type for case in eval_cases)
    document_counts = Counter(case.expected_document_name for case in eval_cases)
    tag_counts = Counter(tag for case in eval_cases for tag in case.tags)

    return {
        "total_cases": len(eval_cases),
        "distinct_document_count": len(document_counts),
        "policy_category_counts": dict(sorted(policy_category_counts.items())),
        "question_type_counts": dict(sorted(question_type_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items())),
    }


def build_output(
    *,
    project_root: Path,
    eval_path: Path,
    eval_cases: list[EvalCaseDefinition],
    strategies: list[VectorSearchStrategyName],
    top_k: int,
    results: list[BenchmarkCaseResult],
) -> dict:
    """组装最终输出 JSON，便于后续归档或直接粘贴进验收记录。"""

    output = {
        "eval_set_file": str(eval_path.relative_to(project_root)).replace("\\", "/"),
        "eval_set_summary": build_eval_set_summary(eval_cases),
        "top_k": top_k,
        "strategies": strategies,
        "strategy_summaries": {
            strategy_name: build_strategy_summary(results, strategy_name)
            for strategy_name in strategies
        },
        "cases": [
            {
                **asdict(item),
                "strategy_results": {
                    strategy_name: {
                        **asdict(strategy_result),
                        "top_hits": [asdict(hit) for hit in strategy_result.top_hits],
                    }
                    for strategy_name, strategy_result in item.strategy_results.items()
                },
            }
            for item in results
        ],
    }

    if {"exact", "hnsw"}.issubset(strategies):
        output["comparison_summary"] = build_comparison_summary(results)

    return output


def main() -> None:
    """执行 Milestone C / Step C4 的最小 benchmark，并输出 JSON 结果。"""

    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    eval_path = project_root / args.eval_set
    eval_cases = load_eval_cases(eval_path)
    results = run_benchmark(
        eval_cases,
        strategies=args.strategies,
        top_k=args.top_k,
    )
    output = build_output(
        project_root=project_root,
        eval_path=eval_path,
        eval_cases=eval_cases,
        strategies=args.strategies,
        top_k=args.top_k,
        results=results,
    )
    output_text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        output_path = project_root / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
    print(output_text)


if __name__ == "__main__":
    main()
