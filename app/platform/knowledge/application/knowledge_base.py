from __future__ import annotations

from app.platform.knowledge.application.contracts import (
    KnowledgeBaseOverviewResult,
    RagMvpStatusResult,
)
from app.platform.knowledge.ports.read_port import KnowledgeDocument, KnowledgeReadPort


class KnowledgeBaseService:
    """知识库概览与文档目录用例。"""

    def __init__(self, read_port: KnowledgeReadPort) -> None:
        self.read_port = read_port

    def get_overview(self) -> KnowledgeBaseOverviewResult:
        return KnowledgeBaseOverviewResult(
            phase="rag-mvp",
            mvp_scope=("样本文档入库", "切块检索", "LLM 问答", "知识库维护", "检索评估"),
            current_categories=("company_policy", "pricing_standard"),
            current_focus="围绕制度样本和价格样本搭建第一版 RAG MVP。",
            next_focus="补齐入库流程、维护界面和检索评估样本集。",
        )

    def get_rag_mvp_status(self) -> RagMvpStatusResult:
        return RagMvpStatusResult(
            indexing_table_ready=True,
            sample_categories=("18-company-policy", "pricing-standard"),
            backend_goal="打通入库、切块、检索、回答整条链路。",
            frontend_goal="提供文档列表、详情、检索调试和问答界面。",
            evaluation_goal="准备一套小规模检索相关性基准集。",
        )

    def list_documents(
        self,
        *,
        search: str | None = None,
        policy_category: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeDocument]:
        if limit < 1:
            raise ValueError("文档数量上限必须为正整数。")
        return self.read_port.list_documents(
            search=search,
            policy_category=policy_category,
            limit=limit,
        )
