from __future__ import annotations

from app.business.online.contracts import AnswerResult, AskKnowledgeCommand
from app.interfaces.http.schemas import (
    AnswerCitation,
    RagAskRequest,
    RagAskResponse,
    RetrievalDebugInfo,
    RetrievalFilters,
    RetrievalHit,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalStageDebug,
)
from app.platform.knowledge.ports.read_port import KnowledgeQueryResult


def search_command(request: RetrievalSearchRequest) -> AskKnowledgeCommand:
    """将 HTTP 检索 Schema 组装成在线应用内部命令。"""
    return AskKnowledgeCommand(
        query=request.query,
        top_k=request.top_k,
        policy_category=request.policy_category,
        responsible_department=request.responsible_department,
        document_id=request.document_id,
        include_history=request.include_history,
        retrieval_mode=request.retrieval_mode,
    )


def ask_command(request: RagAskRequest) -> AskKnowledgeCommand:
    """将 HTTP 问答 Schema 组装成在线应用内部命令。"""
    return AskKnowledgeCommand(
        query=request.query,
        top_k=request.top_k,
        policy_category=request.policy_category,
        responsible_department=request.responsible_department,
        document_id=request.document_id,
        include_history=request.include_history,
        retrieval_mode=request.retrieval_mode,
    )


def search_response(result: KnowledgeQueryResult) -> RetrievalSearchResponse:
    return RetrievalSearchResponse(
        query=result.query,
        top_k=result.top_k,
        filters=RetrievalFilters(
            policy_category=result.policy_category,
            responsible_department=result.responsible_department,
            document_id=result.document_id,
            include_history=result.include_history,
        ),
        hits=[_hit_response(hit) for hit in result.hits],
        debug=RetrievalDebugInfo(
            pipeline=result.pipeline,
            strategy=result.strategy,
            min_score=result.min_score,
            stages=[
                RetrievalStageDebug(
                    name=trace.name,
                    source=trace.source,
                    input_count=trace.input_count,
                    output_count=trace.output_count,
                    details=trace.details,
                )
                for trace in result.traces
            ],
        ),
    )


def ask_response(result: AnswerResult) -> RagAskResponse:
    return RagAskResponse(
        query=result.query,
        answer=result.answer,
        model=result.model,
        citations=[
            AnswerCitation(
                ref_no=citation.ref_no,
                document_id=citation.document_id,
                version_id=citation.version_id,
                chunk_id=citation.chunk_id,
                policy_name=citation.policy_name,
                section_title=citation.section_title,
                page_no=citation.page_no,
                quote=citation.quote,
                source_path=citation.source_path,
                file_name=citation.file_name,
            )
            for citation in result.citations
        ],
        hits=[_hit_response(hit) for hit in result.hits],
        debug=search_response(result.knowledge).debug if result.knowledge is not None else None,
    )


# 内部命中对象字段统一，避免在组装器中重复声明协议类型。
def _hit_response(hit) -> RetrievalHit:  # noqa: ANN001
    return RetrievalHit(
        document_id=hit.document_id,
        version_id=hit.version_id,
        chunk_id=hit.chunk_id,
        policy_name=hit.policy_name,
        policy_category=hit.policy_category,
        responsible_department=hit.responsible_department,
        version_label=hit.version_label,
        section_title=hit.section_title,
        section_path=hit.section_path,
        page_no=hit.page_no,
        chunk_text=hit.chunk_text,
        score=round(hit.score, 6),
        rank=hit.rank,
        source_path=hit.source_path,
        file_name=hit.file_name,
        retrieval_source=hit.retrieval_source,
        score_breakdown={key: round(value, 6) for key, value in hit.score_breakdown.items()},
    )
