from __future__ import annotations

from app.platform.knowledge.ports.write_port import KnowledgeWritePort, KnowledgeWriteResult


class KnowledgeBaseWriteCapability:
    """知识库写入能力，隔离入库用例与具体写端口。"""

    def __init__(self, write_port: KnowledgeWritePort) -> None:
        self.write_port = write_port

    def write(self, **kwargs: object) -> KnowledgeWriteResult:
        """通过知识写端口保存文档版本及其结构化内容。"""
        # 入库应用只依赖这个能力，不直接接触具体仓储或数据库会话。
        return self.write_port.save_document_version_blocks_sections_and_chunks(**kwargs)
