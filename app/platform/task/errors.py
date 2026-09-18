"""Task 生命周期领域可识别的错误。"""


class TaskNotFoundError(LookupError):
    """目标 Task 不存在。"""


class TaskStateTransitionError(RuntimeError):
    """命令不满足当前 Task 状态的转换前提。"""


class TaskIdempotencyConflictError(ValueError):
    """同一幂等标识被用于不一致的命令输入。"""


class TaskLeaseRejectedError(PermissionError):
    """Attempt 不再持有可写入任务状态的有效 lease。"""


class TaskSchemaUnavailableError(RuntimeError):
    """Task PostgreSQL 表结构尚未初始化。"""
