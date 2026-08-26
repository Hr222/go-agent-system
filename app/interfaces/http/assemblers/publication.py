"""知识版本发布接口的输入输出组装器。"""

from app.interfaces.http.schemas.publication import (
    KnowledgePublicationRequest,
    KnowledgePublicationResponse,
)
from app.platform.knowledge.application.publication_service import KnowledgePublicationResult


def publication_arguments(request: KnowledgePublicationRequest) -> tuple[int, int]:
    """提取发布用例需要的内部标识，不向应用层传递 HTTP Schema。"""
    return request.document_id, request.version_id


def publication_response(result: KnowledgePublicationResult) -> KnowledgePublicationResponse:
    """将发布用例结果转换为 HTTP 响应模型。"""
    return KnowledgePublicationResponse(
        document_id=result.document_id,
        version_id=result.version_id,
        version_status=result.version_status,
    )
