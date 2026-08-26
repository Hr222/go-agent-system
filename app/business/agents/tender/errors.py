from __future__ import annotations


class TenderError(RuntimeError):
    """Tender Agent 业务能力的稳定错误基类。"""


class TenderInputError(TenderError):
    """输入文件或用户输入不符合 Tender 契约。"""


class TenderDocumentParseError(TenderError):
    """招标 DOCX 无法解析。"""


class TenderAnalysisError(TenderError):
    """招标分析结果无法通过业务契约校验。"""


class TenderRenderError(TenderError):
    """投标骨架文件生成失败。"""

