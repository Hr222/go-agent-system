from __future__ import annotations

from app.platform.ingestion.contracts import PolicyPipelineRequest, PolicyPipelineResponse
from app.platform.ingestion.pipeline import PolicyPipelineService


class IngestionUseCase:
    """独立文档入库应用用例。"""

    def __init__(self, pipeline: PolicyPipelineService) -> None:
        self.pipeline = pipeline

    def preview(self, request: PolicyPipelineRequest) -> PolicyPipelineResponse:
        """执行不写入知识库的预览链路。"""
        return self.pipeline.preview(request)

    def ingest(self, request: PolicyPipelineRequest) -> PolicyPipelineResponse:
        """执行包含知识库写入的完整入库链路。"""
        return self.pipeline.ingest(request)
