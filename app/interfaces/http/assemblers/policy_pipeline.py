"""文档入库接口与入库应用契约之间的转换器。"""

from app.interfaces.http.schemas.policy_pipeline_document import PolicyPipelineRequest
from app.interfaces.http.schemas.policy_pipeline_response import PolicyPipelineResponse
from app.platform.ingestion.contracts import (
    PolicyPipelineRequest as IngestionPipelineRequest,
)
from app.platform.ingestion.contracts import (
    PolicyPipelineResponse as IngestionPipelineResponse,
)


def pipeline_command(request: PolicyPipelineRequest) -> IngestionPipelineRequest:
    """隔离 HTTP Schema，避免入库模块直接依赖 FastAPI/Pydantic 请求对象。"""
    return IngestionPipelineRequest(
        source_path=request.source_path,
        policy_category=request.policy_category,
        responsible_department=request.responsible_department,
        version_label=request.version_label,
        target_document_id=request.target_document_id,
    )


def pipeline_response(result: IngestionPipelineResponse) -> PolicyPipelineResponse:
    """将入库用例结果转换为前端可消费的 HTTP 响应。"""
    return PolicyPipelineResponse.model_validate(result.model_dump())
