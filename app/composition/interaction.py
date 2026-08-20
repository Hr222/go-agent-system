"""平台能力目录与 Agent Runtime 的 Composition Root。"""

from __future__ import annotations

import base64
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.infrastructure.persistence.repositories.platform_capability_repository import (
    PlatformCapabilityRepository,
)
from app.modules.agent.runtime import AgentRuntime
from app.modules.agent.tender.application.service import TenderApplication
from app.modules.agent.tender.contracts import (
    TenderExtractFormatSectionCommand,
    TenderGenerateSkeletonCommand,
    TenderVerifyExtractionBoundaryCommand,
)
from app.modules.interaction.application.agent_call_policy import AgentCallPolicyValidator
from app.modules.interaction.application.agent_dispatch import AgentCallDispatcher
from app.modules.interaction.application.candidate_retrieval import CapabilityCandidateRetrieval
from app.modules.interaction.application.catalog import PlatformCapabilityCatalog
from app.modules.interaction.application.dispatch import (
    CapabilityDispatchBinding,
    CapabilityDispatchRegistry,
)
from app.modules.interaction.application.gateway import (
    ControlledDispatcher,
    DispatchHandler,
)
from app.modules.interaction.domain.attachment import ResolvedAttachment
from app.modules.interaction.ports.capability_catalog import CapabilityCatalogPort
from app.modules.llm.application.chat import ChatApplication, ChatCommand
from app.modules.llm.ports import TextEmbeddingPort
from app.modules.online.application.ask_knowledge import AskKnowledgeUseCase
from app.modules.online.application.policy_decision import PolicyDecisionApplicationService
from app.modules.online.contracts import AskKnowledgeCommand
from app.modules.online.domain.decision_result import DecisionReviewCommand
from app.shared.config import settings


def build_capability_catalog_repository(session: Session) -> PlatformCapabilityRepository:
    return PlatformCapabilityRepository(session)


def build_capability_dispatch_registry() -> CapabilityDispatchRegistry:
    """只在代码中声明固定目标，数据库分发键不能创建新的执行入口。"""

    return CapabilityDispatchRegistry(
        (
            CapabilityDispatchBinding(
                dispatch_key="agent.tender.generate_bid_skeleton",
                capability_type="agent",
                use_case_type=TenderApplication,
            ),
            CapabilityDispatchBinding(
                dispatch_key="agent.tender.extract_bid_format_section",
                capability_type="agent",
                use_case_type=TenderApplication,
            ),
            CapabilityDispatchBinding(
                dispatch_key="agent.tender.verify_extraction_boundary",
                capability_type="agent",
                use_case_type=TenderApplication,
            ),
            CapabilityDispatchBinding(
                dispatch_key="llm.chat",
                capability_type="chat",
                use_case_type=ChatApplication,
            ),
            CapabilityDispatchBinding(
                dispatch_key="online.knowledge.ask",
                capability_type="knowledge_qa",
                use_case_type=AskKnowledgeUseCase,
            ),
            CapabilityDispatchBinding(
                dispatch_key="online.policy_decision.review",
                capability_type="policy_decision",
                use_case_type=PolicyDecisionApplicationService,
            ),
        )
    )


def build_platform_capability_catalog(
    repository: PlatformCapabilityRepository,
    dispatch_registry: CapabilityDispatchRegistry,
) -> PlatformCapabilityCatalog:
    catalog = PlatformCapabilityCatalog(repository, dispatch_registry)
    catalog.validate_registered()
    return catalog


def build_agent_runtime(
    capability_catalog: CapabilityCatalogPort,
    *,
    tender_application: Callable[[], TenderApplication],
) -> AgentRuntime:
    return AgentRuntime(
        capability_catalog,
        {
            "agent.tender.generate_bid_skeleton": lambda inputs: _generate_tender_skeleton(
                tender_application(),
                inputs,
            ),
            "agent.tender.extract_bid_format_section": lambda inputs: _extract_tender_format(
                tender_application(),
                inputs,
            ),
            "agent.tender.verify_extraction_boundary": lambda inputs: _verify_tender_boundary(
                tender_application(),
                inputs,
            ),
        },
    )


def build_agent_call_dispatcher(
    capability_catalog: CapabilityCatalogPort,
    *,
    agent_runtime: Callable[[], AgentRuntime],
) -> AgentCallDispatcher:
    """组装 V2 结构化 Agent 调用的策略后分发边界。"""

    return AgentCallDispatcher(
        capability_catalog,
        AgentCallPolicyValidator(capability_catalog),
        agent_runtime(),
    )


def build_capability_candidate_retrieval(
    capability_catalog: CapabilityCatalogPort,
    embedding: TextEmbeddingPort,
) -> CapabilityCandidateRetrieval:
    return CapabilityCandidateRetrieval(capability_catalog, embedding)


def build_controlled_dispatcher(
    capability_catalog: CapabilityCatalogPort,
    *,
    agent_runtime: Callable[[], AgentRuntime],
    chat_application: Callable[[], ChatApplication],
    ask_knowledge_use_case: Callable[[], AskKnowledgeUseCase],
    policy_decision_application_service: Callable[[], PolicyDecisionApplicationService],
) -> ControlledDispatcher:
    """组装目录允许的固定业务目标，不接受外部生成的执行地址。"""

    handlers: dict[str, DispatchHandler] = {
        "llm.chat": lambda inputs: chat_application().execute(
            ChatCommand(message=_required_string(inputs, "message"))
        ),
        "online.knowledge.ask": lambda inputs: ask_knowledge_use_case().execute(
            AskKnowledgeCommand(
                query=_required_string(inputs, "query"),
                top_k=_positive_integer(
                    inputs.get("top_k"),
                    default=settings.rag_answer_top_k,
                ),
                policy_category=_optional_string(inputs.get("policy_category")),
            )
        ),
        "online.policy_decision.review": lambda inputs: _review_policy_decision(
            policy_decision_application_service(),
            inputs,
        ),
    }
    return ControlledDispatcher(
        capability_catalog,
        handlers,
        agent_handler=lambda capability_code, dispatch_key, inputs, principal: (
            agent_runtime().execute(
                capability_code=capability_code,
                dispatch_key=dispatch_key,
                inputs=inputs,
                permissions=principal.permission_tuple(),
            )
        ),
    )


def _generate_tender_skeleton(
    application: TenderApplication,
    inputs: dict[str, object],
) -> object:
    return application.execute(_tender_generate_skeleton_command(inputs))


def _tender_generate_skeleton_command(
    inputs: dict[str, object],
) -> TenderGenerateSkeletonCommand:
    """Adapt either a resolved chat attachment or the legacy Base64 input.

    Only the Interaction Gateway may replace the public attachment ID with a
    ``ResolvedAttachment``.  Its content therefore remains inside the server
    boundary until the Tender application consumes this command.
    """

    if "source_document" in inputs:
        source_document = inputs["source_document"]
        if not isinstance(source_document, ResolvedAttachment):
            raise ValueError("source_document 必须是服务端已解析的附件。")
        return TenderGenerateSkeletonCommand(
            file_name=source_document.reference.file_name,
            content=source_document.content,
            user_focus=_optional_string(inputs.get("user_focus")),
        )

    return TenderGenerateSkeletonCommand(
        file_name=_required_string(inputs, "file_name"),
        content=_decode_tender_content(inputs),
        user_focus=_optional_string(inputs.get("user_focus")),
    )


def _extract_tender_format(
    application: TenderApplication,
    inputs: dict[str, object],
) -> object:
    return application.extract_bid_format_section(
        TenderExtractFormatSectionCommand(
            file_name=_required_string(inputs, "file_name"),
            content=_decode_tender_content(inputs),
            start_block_id=_required_string(inputs, "start_block_id"),
            end_block_id=_required_string(inputs, "end_block_id"),
            output_name=_optional_string(inputs.get("output_name")),
        )
    )


def _verify_tender_boundary(
    application: TenderApplication,
    inputs: dict[str, object],
) -> object:
    return application.verify_extraction_boundary(
        TenderVerifyExtractionBoundaryCommand(
            file_name=_required_string(inputs, "file_name"),
            content=_decode_tender_content(inputs),
            start_block_id=_required_string(inputs, "start_block_id"),
            end_block_id=_required_string(inputs, "end_block_id"),
            context_radius=_positive_integer(inputs.get("context_radius"), default=3),
        )
    )


def _review_policy_decision(
    application: PolicyDecisionApplicationService,
    inputs: dict[str, object],
) -> object:
    return application.review(
        DecisionReviewCommand(
            scenario_code=_required_string(inputs, "scenario_code"),
            submitted_materials=_string_list(inputs, "submitted_materials"),
            top_k=_positive_integer(
                inputs.get("top_k"),
                default=settings.retrieval_top_k_default,
            ),
            document_id=_optional_positive_integer(inputs.get("document_id")),
            include_history=_optional_boolean(inputs.get("include_history"), default=False),
            submitted_materials_provided=True,
        )
    )


def _decode_tender_content(inputs: dict[str, object]) -> bytes:
    encoded_content = _required_string(inputs, "content_base64")
    try:
        content = base64.b64decode(encoded_content, validate=True)
    except ValueError as exc:
        raise ValueError("招标文件内容不是有效的 Base64 编码。") from exc
    if len(content) > settings.tender_upload_max_size_bytes:
        raise ValueError("招标文件超过统一入口大小限制。")
    return content


def _required_string(inputs: dict[str, object], field_name: str) -> str:
    value = inputs.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"缺少有效的 {field_name}。")
    return value.strip()


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("可选文本字段格式无效。")
    normalized = value.strip()
    return normalized or None


def _string_list(inputs: dict[str, object], field_name: str) -> tuple[str, ...]:
    value = inputs.get(field_name)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} 必须是文本列表。")
    return tuple(item.strip() for item in value if item.strip())


def _positive_integer(value: object, *, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError("整数输入必须为正整数。")
    return value


def _optional_positive_integer(value: object) -> int | None:
    if value is None:
        return None
    return _positive_integer(value, default=1)


def _optional_boolean(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError("布尔输入格式无效。")
    return value
