from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import PolicyDocument, PolicyVersion
from app.infrastructure.persistence.schema_health import translate_missing_kb_schema_errors
from app.platform.knowledge.domain import KnowledgePublicationState
from app.platform.knowledge.ports.publication_port import (
    KnowledgePublicationPort,
    KnowledgePublicationRecord,
)


class KnowledgePublicationRepository(KnowledgePublicationPort):
    """基于版本状态和主档 current_version_id 实现知识发布。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    @translate_missing_kb_schema_errors
    def activate_version(
        self,
        *,
        document_id: int,
        version_id: int,
    ) -> KnowledgePublicationRecord:
        version = self.session.scalar(
            select(PolicyVersion).where(
                PolicyVersion.id == version_id,
                PolicyVersion.policy_id == document_id,
            )
        )
        if version is None:
            raise ValueError("指定的知识版本不存在，或不属于该制度文档。")

        document = self.session.get(PolicyDocument, document_id)
        if document is None:
            raise ValueError("指定的制度文档不存在。")

        previous_version_id = document.current_version_id
        if previous_version_id and previous_version_id != version_id:
            previous = self.session.get(PolicyVersion, previous_version_id)
            if previous is not None:
                previous.version_status = KnowledgePublicationState.SUPERSEDED.value

        version.version_status = KnowledgePublicationState.ACTIVE.value
        document.current_version_id = version.id
        document.status = "active"
        self.session.add_all([document, version])
        self.session.commit()
        self.session.refresh(version)
        return KnowledgePublicationRecord(
            document_id=document_id,
            version_id=version.id,
            version_status=version.version_status,
        )
