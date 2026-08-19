from fastapi import APIRouter

from app.interfaces.http.routes import (
    health,
    ingestion_retry,
    interaction,
    knowledge_base,
    knowledge_management,
    knowledge_publication,
    policy_decision,
    policy_ingestion,
    policy_pipeline,
    retrieval,
    tender,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(interaction.router, prefix="/interaction", tags=["interaction"])
api_router.include_router(knowledge_base.router, prefix="/kb", tags=["knowledge-base"])
api_router.include_router(
    knowledge_management.router,
    prefix="/kb",
    tags=["knowledge-management"],
)
api_router.include_router(ingestion_retry.router, prefix="/kb", tags=["ingestion"])
api_router.include_router(
    knowledge_publication.router,
    prefix="/kb",
    tags=["knowledge-publication"],
)
api_router.include_router(policy_decision.router, prefix="/kb", tags=["policy-decision"])
api_router.include_router(policy_ingestion.router, prefix="/kb", tags=["policy-ingestion"])
api_router.include_router(policy_pipeline.router, prefix="/kb", tags=["policy-pipeline"])
api_router.include_router(retrieval.router, prefix="/kb", tags=["retrieval"])
api_router.include_router(tender.router, prefix="/agents/tender", tags=["tender-agent"])
