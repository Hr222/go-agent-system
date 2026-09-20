"""当前同步 Agent Runtime 的执行策略适配器。"""

from __future__ import annotations

from app.platform.interaction.ports.agent_execution import (
    AgentExecutionCommand,
    AgentExecutionOutcome,
    AgentExecutionStrategyPort,
)
from app.platform.interaction.ports.agent_runtime import AgentRuntimePort


class SynchronousAgentRuntimeExecutionStrategy(AgentExecutionStrategyPort):
    """将已授权调用交给现有 Runtime，不引入任务或协议职责。"""

    def __init__(self, agent_runtime: AgentRuntimePort) -> None:
        self._agent_runtime = agent_runtime

    def execute(self, command: AgentExecutionCommand) -> AgentExecutionOutcome:
        output = self._agent_runtime.execute(
            capability_code=command.call.capability_code,
            dispatch_key=command.capability.dispatch_key,
            inputs=dict(command.call.inputs),
            permissions=command.principal.permission_tuple(),
        )
        return AgentExecutionOutcome.completed(output)


__all__ = ["SynchronousAgentRuntimeExecutionStrategy"]
