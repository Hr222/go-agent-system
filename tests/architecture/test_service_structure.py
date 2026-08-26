from app.business.online.application.data_acquisition import (
    ChecklistDataProviderRegistry,
    PolicyDataAcquisitionService,
)
from app.business.online.application.rule_retrieval import PolicyRuleRetrievalService
from app.composition import ApplicationContainer
from app.infrastructure.filesystem.upload_service import PolicyUploadService
from app.infrastructure.llm.llm_client import RagAnswerGenerator
from app.platform.ingestion.pipeline import (
    PolicyIngestionService,
    PolicyPipelineService,
)
from app.platform.knowledge.retrieval import KnowledgeRetrievalService


def test_ingestion_services_are_exported_from_new_package() -> None:
    assert PolicyIngestionService.__name__ == "PolicyIngestionService"
    assert PolicyUploadService.__name__ == "PolicyUploadService"
    assert PolicyPipelineService.__name__ == "PolicyPipelineService"


def test_retrieval_services_are_exported_from_new_package() -> None:
    assert KnowledgeRetrievalService.__name__ == "KnowledgeRetrievalService"
    assert RagAnswerGenerator.__name__ == "RagAnswerGenerator"


def test_rule_retrieval_services_are_exported_from_new_package() -> None:
    assert PolicyRuleRetrievalService.__name__ == "PolicyRuleRetrievalService"


def test_data_acquisition_services_are_exported_from_new_package() -> None:
    assert PolicyDataAcquisitionService.__name__ == "PolicyDataAcquisitionService"
    assert ChecklistDataProviderRegistry.__name__ == "ChecklistDataProviderRegistry"


def test_application_exports_are_available() -> None:
    assert ApplicationContainer.__name__ == "ApplicationContainer"
