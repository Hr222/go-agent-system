from app.interfaces.http.schemas.knowledge_base import (
    KnowledgeBaseOverview,
    PolicyDocumentOption,
    PolicyDocumentOptionList,
    RagMvpStatus,
)
from app.platform.knowledge.application.contracts import (
    KnowledgeBaseOverviewResult,
    RagMvpStatusResult,
)
from app.platform.knowledge.ports.read_port import KnowledgeDocument


def overview_response(result: KnowledgeBaseOverviewResult) -> KnowledgeBaseOverview:
    return KnowledgeBaseOverview(
        phase=result.phase,
        mvp_scope=list(result.mvp_scope),
        current_categories=list(result.current_categories),
        current_focus=result.current_focus,
        next_focus=result.next_focus,
    )


def status_response(result: RagMvpStatusResult) -> RagMvpStatus:
    return RagMvpStatus(
        indexing_table_ready=result.indexing_table_ready,
        sample_categories=list(result.sample_categories),
        backend_goal=result.backend_goal,
        frontend_goal=result.frontend_goal,
        evaluation_goal=result.evaluation_goal,
    )


def documents_response(documents: list[KnowledgeDocument]) -> PolicyDocumentOptionList:
    return PolicyDocumentOptionList(
        items=[
            PolicyDocumentOption(
                document_id=document.document_id,
                policy_name=document.policy_name,
                policy_category=document.policy_category,
                responsible_department=document.responsible_department,
                latest_version_id=document.latest_version_id,
                latest_version_label=document.latest_version_label,
            )
            for document in documents
        ]
    )
