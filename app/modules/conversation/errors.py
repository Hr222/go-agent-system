"""Conversation 模块对外可识别的错误。"""


class ConversationNotFoundError(LookupError):
    """追加消息时目标会话不存在。"""


class ConversationAccessDeniedError(PermissionError):
    """主体缺失、会话不存在或会话不属于当前主体。"""


class ContextBudgetExceededError(ValueError):
    """最新上下文消息无法放入给定预算。"""
