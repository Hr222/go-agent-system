"""独立知识文档入库模块。"""

from app.platform.ingestion.pipeline import (
    PolicyIngestionService,
    PolicyPipelineService,
)

__all__ = ["PolicyIngestionService", "PolicyPipelineService"]
