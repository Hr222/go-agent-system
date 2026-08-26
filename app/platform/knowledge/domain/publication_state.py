from enum import StrEnum


class KnowledgePublicationState(StrEnum):
    """知识版本的发布状态。"""

    DRAFT = "draft"
    APPROVED = "approved"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETIRED = "retired"
