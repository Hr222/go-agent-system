from __future__ import annotations

from app.infrastructure.persistence.repositories.policy_persistence_gateway import (
    PolicyPersistenceGateway,
)
from app.infrastructure.persistence.schema_health import translate_missing_kb_schema_errors
from app.platform.knowledge.ports.write_port import KnowledgeWritePort, KnowledgeWriteResult


class KnowledgeWriteRepository(KnowledgeWritePort):
    """PostgreSQL/pgvector 知识写仓储适配器。"""

    def __init__(self, gateway: PolicyPersistenceGateway) -> None:
        self.gateway = gateway

    @translate_missing_kb_schema_errors
    def save_document_version_blocks_sections_and_chunks(
        self,
        **kwargs: object,
    ) -> KnowledgeWriteResult:
        persisted = self.gateway.save_document_version_blocks_sections_and_chunks(**kwargs)
        return KnowledgeWriteResult(
            document_id=persisted.document.id,
            version_id=persisted.version.id,
            version_seq=persisted.version.version_seq,
            version_label=persisted.version.version_label,
            section_count=len(persisted.sections),
            chunk_count=len(persisted.chunks),
        )
