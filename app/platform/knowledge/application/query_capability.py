from __future__ import annotations

from app.platform.knowledge.ports.read_port import (
    KnowledgeDocument,
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeReadPort,
)


class KnowledgeBaseQueryCapability:
    """知识库查询外观层。

    在线应用只依赖这个能力，不需要知道检索策略、数据库或向量索引如何实现。
    """

    def __init__(self, read_port: KnowledgeReadPort) -> None:
        self.read_port = read_port

    def search(self, query: KnowledgeQuery) -> KnowledgeQueryResult:
        if not query.query.strip():
            raise ValueError("知识查询不能为空。")
        return self.read_port.search(query)

    def list_documents(
        self,
        *,
        search: str | None = None,
        policy_category: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeDocument]:
        return self.read_port.list_documents(
            search=search,
            policy_category=policy_category,
            limit=limit,
        )
