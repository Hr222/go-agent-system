from __future__ import annotations

from app.platform.knowledge.ports.read_port import (
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeQueryTrace,
    KnowledgeSearchHit,
)
from app.platform.knowledge.retrieval.contracts import QueryEmbeddingService, RetrievalRepository
from app.platform.knowledge.retrieval.pipeline import HybridRetrievalPipeline


class KnowledgeRetrievalService:
    """把混合检索 pipeline 结果转换成知识模块内部结果。"""

    def __init__(
        self,
        repository: RetrievalRepository,
        pipeline: HybridRetrievalPipeline | None = None,
        embedding_service: QueryEmbeddingService | None = None,
    ) -> None:
        self.repository = repository
        self.pipeline = pipeline or HybridRetrievalPipeline(
            repository,
            embedding_service=embedding_service,
        )

    def search(self, request: KnowledgeQuery) -> KnowledgeQueryResult:
        pipeline_result = self.pipeline.run(request)
        return KnowledgeQueryResult(
            query=request.query,
            top_k=request.top_k,
            policy_category=request.policy_category,
            responsible_department=request.responsible_department,
            document_id=request.document_id,
            include_history=request.include_history,
            hits=tuple(
                KnowledgeSearchHit(
                    document_id=item.document_id,
                    version_id=item.version_id,
                    chunk_id=item.chunk_id,
                    policy_name=item.policy_name,
                    policy_category=item.policy_category,
                    responsible_department=item.responsible_department,
                    version_label=item.version_label,
                    source_path=item.source_path,
                    file_name=item.file_name,
                    section_title=item.section_title,
                    section_path=item.section_path,
                    page_no=item.page_no,
                    chunk_text=item.chunk_text,
                    score=round(item.score, 6),
                    rank=index,
                    retrieval_source=item.retrieval_source,
                    score_breakdown={
                        key: round(value, 6) for key, value in item.score_breakdown.items()
                    },
                )
                for index, item in enumerate(pipeline_result.hits, start=1)
            ),
            pipeline=pipeline_result.pipeline,
            strategy=pipeline_result.strategy,
            min_score=pipeline_result.min_score,
            traces=tuple(
                KnowledgeQueryTrace(
                    name=trace.name,
                    source=trace.source,
                    input_count=trace.input_count,
                    output_count=trace.output_count,
                    details=trace.details,
                )
                for trace in pipeline_result.traces
            ),
        )
