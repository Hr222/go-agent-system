## Context

当前交互模块已经具备平台能力目录、`AgentRuntime`、`ApprovedCapabilityDispatch` 和 P2.5 的 `AgentCallPolicyValidator`。其中，目录是能力、权限和固定分发键的唯一事实来源；`StructuredAgentCall` 只表达模型产生的调用数据，不包含执行授权。旧的 `ControlledDispatcher` 服务于 V1 统一意图入口，输入是确认提议并同时处理 Agent 与非 Agent 能力，不能直接作为 V2 对话层的 Agent 调用边界。

## Goals / Non-Goals

**Goals:**

- 让 V2 的结构化 Agent 调用经过统一的策略校验后才能执行。
- 在执行前重新读取当前目录和权限，并只把目录固定分发键交给已组装的 Agent Runtime。
- 将执行成功和所有受控失败转换为 `AgentCallResult` 或 `AgentCallError`，不泄漏 Provider、堆栈或执行器对象。
- 保留 `call_id` 及对话关联标识，给后续 Conversation 事件和多轮续写留下插口。

**Non-Goals:**

- 不修改旧 V1 Gateway/Dispatcher，不替换 `ApprovedCapabilityDispatch` 的既有 HTTP 流程。
- 不新增 Dialogue HTTP 路由、Conversation 写入、任务状态、重试、超时调度或幂等存储。
- 不实现 SubAgent、Workflow、并行分发或多目标选择；本 Change 只执行单个 Agent 调用。
- 不让模型、浏览器或数据库记录直接决定执行器、URL、类名或函数名。

## Decisions

### 1. 在 Interaction Application 中新增 V2 Agent 分发服务

新增 `AgentCallDispatcher`，输入为 `StructuredAgentCall`、可信 `RequestPrincipal` 和可选的 `ApprovedCapabilityDispatch`。它先调用 `AgentCallPolicyValidator`，策略结果不是 `authorized` 时立即返回受控状态，不接触 Agent Runtime。这样授权和执行之间有明确的应用层边界，Dialogue Runtime 不需要知道目录或执行器细节。

替代方案是让 Dialogue Runtime 直接调用 `AgentRuntime.execute`，但这会绕过确认策略，也会把权限复核和错误映射散落到对话层，因此不采用。

### 2. 运行时目标只来自当前目录和 Composition Root

策略通过后，分发服务再次读取当前主体可用的 Agent 目录条目，确认能力类型为 `agent`，并取得目录中的 `dispatch_key`。实际处理器仍由 `AgentRuntime` 在 Composition Root 中以静态映射组装；模型输入中的能力代码、旧提议中的键或任何客户端字段都不能创建新的执行入口。

替代方案是将处理器字典暴露给调用方，虽然实现简单，但会形成可注入执行器的安全边界，故不采用。

### 3. 使用结构化结果包装运行时输出

成功时把 JSON 对象、映射或 Pydantic 模型转换为 `AgentCallResult.output`；无法转换为对象时返回 `AGENT_OUTPUT_INVALID`。运行时的 `LookupError`、`ValueError` 和其他异常分别映射为稳定错误码，消息只描述可操作的公开状态。错误对象保留调用关联字段和 `retryable`，但不保存异常原文。

### 4. 本 Change 不做执行状态持久化

一次分发只在当前命令生命周期内执行一次，不写 Conversation 或任务存储，也不自行重试。`call_id` 仅用于结果关联，幂等、重试和恢复由后续 Dialogue/Task Change 决定，避免本 Change 引入新的状态源。

## Risks / Trade-offs

- [目录在策略校验与实际执行之间发生变化] -> 策略服务和 Agent Runtime 都重新读取目录并校验固定键；任一不一致都拒绝执行。
- [Agent Runtime 返回非对象或包含内部对象] -> 分发边界只接受可序列化 JSON 对象，转换失败返回稳定错误码。
- [运行时异常被错误地暴露] -> 统一捕获并映射为有限错误码，日志留在内部，结构化错误不携带堆栈和原始输入。
- [未来需要多 Agent 或 Workflow] -> 保留 `call_id`、`parent_run_id` 和运行时注入接口，但不在本 Change 扩展多目标状态机。

## Migration Plan

先新增应用服务、导出和单元测试，再由 Composition Root 注入已有 `AgentRuntime`。当前 V1 Gateway 不迁移；回滚时移除新服务和测试即可，不影响数据库和对外协议。归档前运行全量测试、OpenSpec 严格校验和 Ruff。

## Open Questions

无。未来是否持久化执行事件、是否支持重试以及如何接入 Dialogue Runtime，分别由后续 Change 决定。
