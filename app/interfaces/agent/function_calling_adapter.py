from __future__ import annotations

from app.business.online.application.ask_knowledge import AskKnowledgeUseCase
from app.business.online.contracts import AskKnowledgeCommand
from app.interfaces.agent.contracts import AskKnowledgeToolArguments, FunctionCallingResult


class FunctionCallingAdapter:
    """向 LangChain/LangGraph 暴露稳定的工具调用入口。"""

    def __init__(self, use_case: AskKnowledgeUseCase) -> None:
        self.use_case = use_case

    def ask_knowledge(self, arguments: AskKnowledgeToolArguments) -> FunctionCallingResult:
        """将 Agent 工具参数转换为在线问答命令，并返回稳定的工具结果。"""
        # 这里只做外部参数适配，不在 Agent 层自行执行检索或调用 LLM。
        command = AskKnowledgeCommand(
            query=str(arguments.get("query", "")),
            top_k=int(arguments.get("top_k", 5)),
            policy_category=_optional_string(arguments.get("policy_category")),
            responsible_department=_optional_string(arguments.get("responsible_department")),
            document_id=_optional_int(arguments.get("document_id")),
            include_history=bool(arguments.get("include_history", False)),
        )
        result = self.use_case.execute(command)
        # 只暴露 Function Calling 所需字段，避免内部领域对象泄漏到外部编排器。
        return {
            "query": result.query,
            "answer": result.answer,
            "model": result.model,
            "citations": [
                {
                    "ref_no": item.ref_no,
                    "document_id": item.document_id,
                    "version_id": item.version_id,
                    "chunk_id": item.chunk_id,
                    "policy_name": item.policy_name,
                    "section_title": item.section_title,
                    "page_no": item.page_no,
                    "quote": item.quote,
                }
                for item in result.citations
            ],
        }


def _optional_string(value: object) -> str | None:
    """把工具参数中的可选值统一清洗为空值或非空字符串。"""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: object) -> int | None:
    """把工具参数中的可选数字转换为整数，保留非法输入的显式错误。"""
    if value is None or value == "":
        return None
    return int(value)
