from __future__ import annotations

from dataclasses import dataclass

from app.platform.knowledge.ports.publication_port import KnowledgePublicationPort


@dataclass(slots=True, frozen=True)
class KnowledgePublicationResult:
    document_id: int
    version_id: int
    version_status: str


class KnowledgePublicationService:
    """知识版本发布用例，和文档解析/入库流程保持独立。"""

    def __init__(self, publication_port: KnowledgePublicationPort) -> None:
        self.publication_port = publication_port

    def publish(self, *, document_id: int, version_id: int) -> KnowledgePublicationResult:
        if document_id < 1 or version_id < 1:
            raise ValueError("document_id 和 version_id 必须为正整数。")
        version = self.publication_port.activate_version(
            document_id=document_id,
            version_id=version_id,
        )
        return KnowledgePublicationResult(
            document_id=document_id,
            version_id=version_id,
            version_status=str(getattr(version, "version_status", "active")),
        )
