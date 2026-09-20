## Why

当前 `AgentCallDispatcher` 已经承担能力目录、策略校验、运行时调用和结果投影，但执行路径被固定为同步 `AgentRuntime`。后续 MCP、Task、SubAgent 和 Workflow 都需要复用同一套授权与结果边界；现在先抽出受控的执行策略插口，可以避免把 Tender 或某一种协议固化成平台实现。

## What Changes

- 为已授权 Agent 调用定义协议无关的执行策略边界。
- 让 `AgentCallDispatcher` 通过 Composition Root 注入当前执行策略；现有同步 `AgentRuntime` 作为默认实现。
- 保留现有目录复核、权限/确认校验、固定 `dispatch_key`、安全错误和附件结果投影行为。
- 保留 `StructuredAgentCall` 的调用关联字段，并将其传递给执行策略，供后续异步调用、SubAgent 和 Workflow 建立关联。
- 用替身执行策略验证未来可以增加新的执行模式，而无需修改协议适配器、业务 Agent 或 Task Domain。
- 不在本 Change 中实现 MCP 迁移、异步 Task 提交、Tender Task Executor、SubAgent、Workflow 或 LangGraph。

## Capabilities

### New Capabilities

- `agent-call-execution-strategy`: 为已授权 Agent 调用提供可替换、协议无关的执行策略契约，并规定默认同步策略的兼容行为。

### Modified Capabilities

- `controlled-agent-dispatch`: 将执行目标从固定的同步调用路径收敛为由 Composition 注入的受控执行策略，同时保持授权、固定分发键和安全结果边界不变。

## Impact

- 影响 `app/platform/interaction/application/agent_dispatch.py`、相关 Ports 和 `app/composition/interaction.py` 的对象组装。
- 可能增加 Agent 调用执行结果的内部中间契约，但不改变现有 MCP、HTTP 或 Chat 外部接口。
- 不新增数据库表、字段、Task 状态或持久化事务；不改变 Task Management 状态机和幂等语义。
- 不引入新的 Provider、第三方 Agent 框架或运行时动态注册机制。
- 需要补充 Agent 分发单元测试和架构边界测试，证明策略只能由 Composition 注入且业务 Agent 不依赖 Task、HTTP 或 ORM。
