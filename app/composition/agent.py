"""Agent 应用能力的 Composition Root。"""

from app.composition.llm import build_structured_llm
from app.infrastructure.documents.tender_docx import (
    TenderDocxReader,
    TenderDocxSkeletonRenderer,
)
from app.infrastructure.llm.openai_client_factory import OpenAICompatibleClientFactory
from app.modules.agent.tender.application.chunking import TenderChunkPlanner
from app.modules.agent.tender.application.service import TenderApplication
from app.modules.agent.tender.contracts import TenderAnalysisBudget
from app.modules.agent.tender.ports.document_port import TenderDocumentReaderPort
from app.modules.agent.tender.ports.renderer_port import TenderSkeletonRendererPort
from app.modules.llm.contracts import StructuredLlmPort
from app.shared.config import settings


def build_tender_structured_llm(
    client_factory: OpenAICompatibleClientFactory,
) -> StructuredLlmPort:
    """组装 Tender 使用的当前 Provider 结构化 LLM 适配器。"""

    return build_structured_llm(client_factory)


def build_tender_application(
    structured_llm: StructuredLlmPort,
    *,
    reader: TenderDocumentReaderPort | None = None,
    renderer: TenderSkeletonRendererPort | None = None,
) -> TenderApplication:
    """组装 Tender Application 及其文档处理适配器。"""

    return TenderApplication(
        llm=structured_llm,
        boundary_llm=structured_llm,
        verify_llm=structured_llm,
        planner=TenderChunkPlanner(),
        budget=TenderAnalysisBudget(
            chunk_input_chars=settings.tender_chunk_input_chars,
            merge_input_chars=settings.tender_merge_input_chars,
            max_output_chars=settings.tender_max_output_chars,
            max_chunks=settings.tender_max_chunks,
            max_merge_items=settings.tender_max_merge_items,
            max_llm_calls=settings.tender_max_llm_calls,
            max_retries=settings.tender_max_retries,
            max_total_seconds=settings.tender_max_total_seconds,
        ),
        reader=reader
        or TenderDocxReader(
            max_bytes=settings.tender_upload_max_size_bytes,
            hard_max_bytes=settings.tender_hard_max_size_bytes,
            max_uncompressed_bytes=settings.tender_max_uncompressed_bytes,
            max_zip_entries=settings.tender_max_zip_entries,
            max_compression_ratio=settings.tender_max_compression_ratio,
        ),
        renderer=renderer or TenderDocxSkeletonRenderer(),
    )
