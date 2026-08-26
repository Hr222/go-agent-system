from __future__ import annotations

from app.platform.knowledge.ports.quality_audit import (
    KnowledgeQualityAuditPort,
    KnowledgeQualityAuditReport,
)


class KnowledgeQualityAuditService:
    """知识库 E1/E2 收尾服务，只负责调用只读审计端口。"""

    def __init__(self, audit_port: KnowledgeQualityAuditPort) -> None:
        self.audit_port = audit_port

    def audit(self) -> KnowledgeQualityAuditReport:
        return self.audit_port.audit()
