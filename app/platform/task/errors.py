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


class TaskSubmissionPrincipalError(PermissionError):
    """提交任务的主体不是可用于确定资源归属的可信主体。"""


class TaskSubmissionPolicyError(ValueError):
    """受信任提交不满足服务端固定的任务策略。"""


class TaskExecutorUnavailableError(RuntimeError):
    """任务类型没有服务端注册的执行器。"""


class TaskAccessDeniedError(PermissionError):
    """请求主体不能访问 Task 管理能力。"""


class TaskUnavailableError(LookupError):
    """Task 不存在或不属于当前主体。"""
