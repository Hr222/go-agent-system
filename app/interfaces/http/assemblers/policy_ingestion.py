"""候选文件扫描接口的输入输出组装器。"""

from app.interfaces.http.schemas.policy_ingestion import (
    PolicyScanRequest,
    PolicyScanResponse,
)
from app.platform.ingestion.contracts import (
    PolicyScanRequest as IngestionScanRequest,
)
from app.platform.ingestion.contracts import (
    PolicyScanResponse as IngestionScanResponse,
)


def scan_command(request: PolicyScanRequest) -> IngestionScanRequest:
    """将 HTTP 请求转换为入库模块内部扫描命令。"""
    return IngestionScanRequest(
        source_root=request.source_root,
        limit=request.limit,
    )


def scan_response(result: IngestionScanResponse) -> PolicyScanResponse:
    """将入库模块结果转换为 HTTP 响应模型。"""
    return PolicyScanResponse.model_validate(result.model_dump())
