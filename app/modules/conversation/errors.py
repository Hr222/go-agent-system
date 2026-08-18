"""Conversation 模块对外可识别的错误。"""


class ConversationNotFoundError(LookupError):
    """追加消息时目标会话不存在。"""


class ContextBudgetExceededError(ValueError):
    """最新上下文消息无法放入给定预算。"""
