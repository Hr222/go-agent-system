from app.platform.knowledge.application.quality_audit import KnowledgeQualityAuditService
from app.platform.knowledge.ports.quality_audit import (
    KnowledgeAuditIssue,
    KnowledgeQualityAuditReport,
)


class FakeQualityAuditPort:
    def __init__(self, report: KnowledgeQualityAuditReport) -> None:
        self.report = report
        self.call_count = 0

    def audit(self) -> KnowledgeQualityAuditReport:
        self.call_count += 1
        return self.report


def test_quality_audit_service_returns_read_only_report() -> None:
    report = KnowledgeQualityAuditReport(
        document_count=1,
        version_count=2,
        section_count=3,
        block_count=4,
        chunk_count=5,
        document_status_counts={"draft": 1},
        version_status_counts={"draft": 2},
        parser_status_counts={"parsed": 2},
        current_version_count=0,
        latest_version_count=1,
        issues=(
            KnowledgeAuditIssue(
                code="source_file_missing",
                severity="warning",
                entity_type="version",
                entity_id=2,
                message="源文件不可访问。",
            ),
        ),
    )
    port = FakeQualityAuditPort(report)

    result = KnowledgeQualityAuditService(port).audit()

    assert result is report
    assert result.issue_count == 1
    assert result.issue_counts == {"source_file_missing": 1}
    assert port.call_count == 1
