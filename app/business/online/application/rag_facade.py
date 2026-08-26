from __future__ import annotations

from app.business.online.contracts import AnswerResult, AskKnowledgeCommand
from app.business.online.ports import AnswerGenerator
from app.platform.knowledge.application.query_capability import KnowledgeBaseQueryCapability
from app.platform.knowledge.ports.read_port import KnowledgeQueryResult

INSUFFICIENT_EVIDENCE_ANSWER = "未在知识库中找到足够依据。"


class RagApplicationFacade:
    """在线 RAG 外观层。

    HTTP 和 Function Calling 都通过这里进入知识查询与回答能力；外部接口不再直接
    组装检索 pipeline 或触碰仓储。
    """

    def __init__(
        self,
        *,
        knowledge_query: KnowledgeBaseQueryCapability,
        answer_generator: AnswerGenerator,
    ) -> None:
        self.knowledge_query = knowledge_query
        self.answer_generator = answer_generator

    def search(self, command: AskKnowledgeCommand) -> KnowledgeQueryResult:
        """通过知识查询能力执行检索，供 search 和 ask 共享同一条链路。"""
        return self.knowledge_query.search(command.as_knowledge_query())

    def ask(self, command: AskKnowledgeCommand) -> AnswerResult:
        """先获取可引用证据，命中后再调用回答生成端口。"""
        knowledge = self.search(command)
        if not knowledge.hits:
            return AnswerResult(
                query=command.query,
                answer=INSUFFICIENT_EVIDENCE_ANSWER,
                model=None,
                citations=(),
                hits=(),
                knowledge=knowledge,
            )

        answer = self.answer_generator.answer(
            query=command.query,
            hits=list(knowledge.hits),
        )
        if answer.answer.strip() == INSUFFICIENT_EVIDENCE_ANSWER:
            return AnswerResult(
                query=answer.query,
                answer=answer.answer,
                model=answer.model,
                citations=(),
                hits=(),
                knowledge=knowledge,
            )
        return AnswerResult(
            query=answer.query,
            answer=answer.answer,
            model=answer.model,
            citations=answer.citations,
            hits=answer.hits,
            knowledge=knowledge,
        )
