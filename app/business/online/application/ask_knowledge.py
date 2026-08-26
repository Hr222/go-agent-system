from __future__ import annotations

from app.business.online.application.rag_facade import RagApplicationFacade
from app.business.online.contracts import AnswerResult, AskKnowledgeCommand
from app.platform.knowledge.ports.read_port import KnowledgeQueryResult


class AskKnowledgeUseCase:
    """在线知识问答用例入口。"""

    def __init__(self, facade: RagApplicationFacade) -> None:
        self.facade = facade

    def execute(self, command: AskKnowledgeCommand) -> AnswerResult:
        """执行检索后问答链路。"""
        return self.facade.ask(command)

    def search(self, command: AskKnowledgeCommand) -> KnowledgeQueryResult:
        """只执行知识检索，不触发回答模型调用。"""
        return self.facade.search(command)
