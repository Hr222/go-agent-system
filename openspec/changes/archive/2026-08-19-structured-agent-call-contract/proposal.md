## Why

当前 V1 的 `IntentAssessment`、确认提议和 Dispatcher 之间使用的是面向旧交互入口的对象，不能直接表达 Dialogue Runtime 中“模型请求调用一个 Agent、Gateway 审核、Agent Runtime 返回结果”的边界。V2 需要先固定一个不携带执行权的结构化 Agent Call 契约，后续策略校验、受控分发和对话续写才能独立演化。

## What Changes

- 新增 `StructuredAgentCall`：表达模型或上层编排产生的单次 Agent 调用意图，包含调用标识、目录能力代码、经过模型 Schema 约束的输入和可选的链路关联标识。
- 新增 `AgentCallResult` 与 `AgentCallError`：以统一、可序列化的方式表达 Agent Runtime 的成功输出和受控失败，保留能力代码与调用标识用于后续 Conversation 事件和 LLM 续写关联。
- 固化数据边界：调用契约不得包含目录分发键、Provider/SDK 对象、可执行 URL、函数名、权限或用户确认状态；结果契约不得泄漏异常堆栈或底层实现细节。
- 补充领域契约校验和回归测试，并从 `interaction` 模块公开该契约供后续 P2.5、P2.6 消费。

## Capabilities

### New Capabilities

- `structured-agent-call-contract`：定义 LLM、Interaction Gateway 和 Agent Runtime 间的类型化单 Agent 调用、结果与错误数据契约。

### Modified Capabilities

- 无。

## Impact

- 新增 `app/modules/interaction/domain/agent_call.py` 及其公开导出，新增针对领域不变量的测试。
- 不新增 HTTP 接口、数据库表、Redis、Conversation 事件写入、模型调用、确认策略或 Agent 实际分发。
- 不修改现有 V1 `IntentInteractionGateway`、`ConfirmationProposal`、`ApprovedCapabilityDispatch` 或 `/api/v1/llm/chat` 的兼容行为；后续 P2.5、P2.6 在新契约上实现策略校验和受控分发。
