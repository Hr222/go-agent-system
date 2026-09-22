from __future__ import annotations

from functools import wraps
from typing import ParamSpec, TypeVar

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.shared.exceptions import KnowledgeBaseSchemaUnavailableError

P = ParamSpec("P")
R = TypeVar("R")

# 启动阶段要覆盖到当前入库链路真正依赖的全部核心表，
# 避免应用启动正常、首次入库才因为缺表而失败。
REQUIRED_KB_TABLES = (
    "kb_policy_document",
    "kb_policy_version",
    "kb_policy_block",
    "kb_policy_section",
    "kb_policy_chunk",
)

# Task 生命周期由四张表组成；缺任一张都会让列表、事件或命令路径不完整。
REQUIRED_TASK_TABLES = (
    "task",
    "task_attempt",
    "task_event",
    "task_command_receipt",
)

KB_SCHEMA_SETUP_GUIDE = (
    "知识库数据表尚未初始化。请先执行 sql/001_kb_policy_schema.sql，"
    "如需确认 embedding 维度，再执行 sql/002_kb_policy_chunk_embedding_dimension_1024.sql，"
    "如已接入 block/OCR 流程，还需要执行 sql/003_kb_policy_block.sql。"
    "如需启用 HNSW 向量索引，再执行 sql/004_kb_policy_chunk_embedding_hnsw.sql。"
)

TASK_SCHEMA_SETUP_GUIDE = "Task 数据表尚未初始化。请先执行 sql/013_task_lifecycle.sql。"


def find_missing_kb_tables(engine: Engine) -> list[str]:
    inspector = inspect(engine)
    return [table for table in REQUIRED_KB_TABLES if not inspector.has_table(table)]


def is_kb_schema_ready(engine: Engine) -> bool:
    return not find_missing_kb_tables(engine)


def is_missing_kb_schema_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        ("undefinedtable" in message or "does not exist" in message)
        and "kb_policy_" in message
    )


def translate_missing_kb_schema_errors(func):  # noqa: ANN001
    """把数据库缺表错误转换为应用层可识别的异常。"""

    @wraps(func)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as exc:
            if is_missing_kb_schema_error(exc):
                raise KnowledgeBaseSchemaUnavailableError(KB_SCHEMA_SETUP_GUIDE) from exc
            raise

    return wrapped


def safe_find_missing_kb_tables(engine: Engine) -> list[str] | None:
    try:
        return find_missing_kb_tables(engine)
    except SQLAlchemyError:
        return None


def find_missing_task_tables(engine: Engine) -> list[str]:
    """返回缺失的 Task 生命周期表；该检查只读取数据库元数据。"""

    inspector = inspect(engine)
    return [table for table in REQUIRED_TASK_TABLES if not inspector.has_table(table)]


def safe_find_missing_task_tables(engine: Engine) -> list[str] | None:
    """隐藏数据库不可用细节，供启动诊断消费。"""

    try:
        return find_missing_task_tables(engine)
    except SQLAlchemyError:
        return None
