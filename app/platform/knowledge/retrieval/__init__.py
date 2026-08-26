"""检索链路职责包导出。

这里集中暴露当前检索主链路涉及的核心对象，方便调用方按职责引用：
- `HybridRetrievalPipeline`：负责整体检索编排
- `HybridHitFusionService`：负责双路召回结果融合
- `HeuristicRetrievalReranker`：负责启发式重排
- `KnowledgeRetrievalService`：负责检索结果到接口响应的映射
"""

from app.platform.knowledge.retrieval.fusion import HybridHitFusionService
from app.platform.knowledge.retrieval.models import RetrievalPipelineResult, RetrievalStageTrace
from app.platform.knowledge.retrieval.pipeline import (
    ExactVectorRetrievalPipeline,
    HybridRetrievalPipeline,
)
from app.platform.knowledge.retrieval.policies import (
    PolicyRetrievalQueryPolicy,
    RetrievalKeywordPlan,
)
from app.platform.knowledge.retrieval.rerank import HeuristicRetrievalReranker
from app.platform.knowledge.retrieval.service import KnowledgeRetrievalService
from app.platform.knowledge.retrieval.vector_search import (
    ExactVectorSearchStrategy,
    HnswVectorSearchStrategy,
    build_vector_search_strategy,
)

__all__ = [
    "ExactVectorRetrievalPipeline",
    "ExactVectorSearchStrategy",
    "HeuristicRetrievalReranker",
    "HybridHitFusionService",
    "HybridRetrievalPipeline",
    "HnswVectorSearchStrategy",
    "KnowledgeRetrievalService",
    "PolicyRetrievalQueryPolicy",
    "RetrievalPipelineResult",
    "RetrievalKeywordPlan",
    "RetrievalStageTrace",
    "build_vector_search_strategy",
]
