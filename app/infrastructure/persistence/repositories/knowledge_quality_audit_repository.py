from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import (
    PolicyBlock,
    PolicyChunk,
    PolicyDocument,
    PolicySection,
    PolicyVersion,
)
from app.platform.knowledge.ports.quality_audit import (
    KnowledgeAuditIssue,
    KnowledgeQualityAuditPort,
    KnowledgeQualityAuditReport,
)


class KnowledgeQualityAuditRepository(KnowledgeQualityAuditPort):
    """PostgreSQL 知识库只读审计适配器。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def audit(self) -> KnowledgeQualityAuditReport:
        documents = list(self.session.scalars(select(PolicyDocument).order_by(PolicyDocument.id)))
        versions = list(self.session.scalars(select(PolicyVersion).order_by(PolicyVersion.id)))
        sections = list(self.session.scalars(select(PolicySection).order_by(PolicySection.id)))
        blocks = list(self.session.scalars(select(PolicyBlock).order_by(PolicyBlock.id)))
        chunks = list(self.session.scalars(select(PolicyChunk).order_by(PolicyChunk.id)))

        issues: list[KnowledgeAuditIssue] = []
        self._append_document_issues(documents, issues)
        self._append_version_issues(versions, issues)
        self._append_section_issues(sections, issues)
        self._append_block_issues(blocks, issues)
        self._append_chunk_issues(chunks, sections, issues)
        self._append_duplicate_issues(versions, issues)

        return KnowledgeQualityAuditReport(
            document_count=len(documents),
            version_count=len(versions),
            section_count=len(sections),
            block_count=len(blocks),
            chunk_count=len(chunks),
            document_status_counts=self._status_counts(documents, "status"),
            version_status_counts=self._status_counts(versions, "version_status"),
            parser_status_counts=self._status_counts(versions, "parser_status"),
            current_version_count=sum(item.current_version_id is not None for item in documents),
            latest_version_count=sum(item.latest_version_id is not None for item in documents),
            issues=tuple(issues),
        )

    @staticmethod
    def _status_counts(items: Iterable[object], attribute: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            value = getattr(item, attribute) or "<empty>"
            counts[value] = counts.get(value, 0) + 1
        return dict(sorted(counts.items()))

    @staticmethod
    def _is_blank(value: str | None) -> bool:
        return value is None or not value.strip()

    def _append_document_issues(
        self,
        documents: Iterable[PolicyDocument],
        issues: list[KnowledgeAuditIssue],
    ) -> None:
        for document in documents:
            if self._is_blank(document.policy_name):
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_document_name",
                        severity="error",
                        entity_type="document",
                        entity_id=document.id,
                        message="资料主档缺少制度名称。",
                    )
                )
            if self._is_blank(document.policy_category):
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_document_category",
                        severity="error",
                        entity_type="document",
                        entity_id=document.id,
                        message="资料主档缺少制度分类。",
                    )
                )
            if document.latest_version_id is None:
                issues.append(
                    KnowledgeAuditIssue(
                        code="missing_latest_version",
                        severity="error",
                        entity_type="document",
                        entity_id=document.id,
                        message="资料主档没有 latest_version_id。",
                    )
                )

    def _append_version_issues(
        self,
        versions: Iterable[PolicyVersion],
        issues: list[KnowledgeAuditIssue],
    ) -> None:
        for version in versions:
            details = {
                "document_id": version.policy_id,
                "version_id": version.id,
                "source_path": version.source_path,
                "file_name": version.file_name,
            }
            if self._is_blank(version.version_label):
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_version_label",
                        severity="error",
                        entity_type="version",
                        entity_id=version.id,
                        message="资料版本缺少版本标签。",
                        details=details,
                    )
                )
            if self._is_blank(version.source_path):
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_source_path",
                        severity="error",
                        entity_type="version",
                        entity_id=version.id,
                        message="资料版本缺少源文件路径。",
                        details=details,
                    )
                )
            if self._is_blank(version.file_name):
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_file_name",
                        severity="error",
                        entity_type="version",
                        entity_id=version.id,
                        message="资料版本缺少源文件名。",
                        details=details,
                    )
                )
            if self._is_blank(version.file_hash):
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_file_hash",
                        severity="error",
                        entity_type="version",
                        entity_id=version.id,
                        message="资料版本缺少文件哈希。",
                        details=details,
                    )
                )
            if self._is_blank(version.raw_text):
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_raw_text",
                        severity="error",
                        entity_type="version",
                        entity_id=version.id,
                        message="资料版本缺少原始抽取文本。",
                        details=details,
                    )
                )
            if self._is_blank(version.clean_text):
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_clean_text",
                        severity="error",
                        entity_type="version",
                        entity_id=version.id,
                        message="资料版本缺少清洗文本。",
                        details=details,
                    )
                )
            if version.parser_status != "parsed":
                issues.append(
                    KnowledgeAuditIssue(
                        code="parser_not_parsed",
                        severity="error",
                        entity_type="version",
                        entity_id=version.id,
                        message=f"资料版本解析状态为 {version.parser_status}。",
                        details=details,
                    )
                )
            if version.source_path and not Path(version.source_path).exists():
                issues.append(
                    KnowledgeAuditIssue(
                        code="source_file_missing",
                        severity="warning",
                        entity_type="version",
                        entity_id=version.id,
                        message="数据库记录的源文件路径在当前主机不可访问。",
                        details=details,
                    )
                )

    def _append_section_issues(
        self,
        sections: Iterable[PolicySection],
        issues: list[KnowledgeAuditIssue],
    ) -> None:
        for section in sections:
            if self._is_blank(section.section_no) and self._is_blank(section.section_title):
                issues.append(
                    KnowledgeAuditIssue(
                        code="section_missing_identifier",
                        severity="warning",
                        entity_type="section",
                        entity_id=section.id,
                        message="章节同时缺少 section_no 和 section_title，需业务确认。",
                        details={"version_id": section.version_id},
                    )
                )
            if self._is_blank(section.section_text):
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_section_text",
                        severity="error",
                        entity_type="section",
                        entity_id=section.id,
                        message="章节缺少正文。",
                        details={"version_id": section.version_id},
                    )
                )

    def _append_block_issues(
        self,
        blocks: Iterable[PolicyBlock],
        issues: list[KnowledgeAuditIssue],
    ) -> None:
        for block in blocks:
            if self._is_blank(block.text) and block.block_type == "text":
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_text_block",
                        severity="warning",
                        entity_type="block",
                        entity_id=block.id,
                        message="文本块缺少正文。",
                        details={"version_id": block.version_id},
                    )
                )

    def _append_chunk_issues(
        self,
        chunks: Iterable[PolicyChunk],
        sections: Iterable[PolicySection],
        issues: list[KnowledgeAuditIssue],
    ) -> None:
        section_ids = {section.id for section in sections}
        for chunk in chunks:
            if self._is_blank(chunk.chunk_text):
                issues.append(
                    KnowledgeAuditIssue(
                        code="empty_chunk_text",
                        severity="error",
                        entity_type="chunk",
                        entity_id=chunk.id,
                        message="检索切块缺少正文。",
                        details={"version_id": chunk.version_id},
                    )
                )
            if chunk.section_id is None or chunk.section_id not in section_ids:
                issues.append(
                    KnowledgeAuditIssue(
                        code="chunk_missing_section",
                        severity="warning",
                        entity_type="chunk",
                        entity_id=chunk.id,
                        message="检索切块没有可关联的章节。",
                        details={"version_id": chunk.version_id, "section_id": chunk.section_id},
                    )
                )

    def _append_duplicate_issues(
        self,
        versions: Iterable[PolicyVersion],
        issues: list[KnowledgeAuditIssue],
    ) -> None:
        versions_list = list(versions)
        hash_groups: dict[str, list[PolicyVersion]] = {}
        label_groups: dict[tuple[int, str], list[PolicyVersion]] = {}
        for version in versions_list:
            if version.file_hash and version.file_hash.strip():
                hash_groups.setdefault(version.file_hash, []).append(version)
            if version.version_label and version.version_label.strip():
                key = (version.policy_id, version.version_label)
                label_groups.setdefault(key, []).append(version)

        for file_hash, group in hash_groups.items():
            if len(group) < 2:
                continue
            for version in group:
                issues.append(
                    KnowledgeAuditIssue(
                        code="duplicate_file_hash",
                        severity="warning",
                        entity_type="version",
                        entity_id=version.id,
                        message="多个版本共享同一文件哈希，疑似重复资料。",
                        details={"file_hash": file_hash, "duplicate_count": len(group)},
                    )
                )

        for (document_id, version_label), group in label_groups.items():
            if len(group) < 2:
                continue
            for version in group:
                issues.append(
                    KnowledgeAuditIssue(
                        code="duplicate_version_label",
                        severity="warning",
                        entity_type="version",
                        entity_id=version.id,
                        message="同一资料主档下存在重复版本标签。",
                        details={
                            "document_id": document_id,
                            "version_label": version_label,
                            "duplicate_count": len(group),
                        },
                    )
                )
