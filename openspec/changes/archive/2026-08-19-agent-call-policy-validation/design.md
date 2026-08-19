## Context

P2.4 的 `StructuredAgentCall` 只表达调用数据，不包含分发键、权限或确认状态。当前代码已有 `PlatformCapabilityCatalog`、`validate_capability_inputs`、`ApprovedCapabilityDispatch` 和请求主体权限，但它们尚未被组合成面向 V2 Agent Call 的独立策略校验入口。P2.5 位于实际 Agent Runtime 之前，负责把不可信的结构化调用变成可解释的策略结果。

## Goals / Non-Goals

**Goals:**

- 从服务端目录重新读取目标能力，确认能力已启用、当前主体有权限且类型为 `agent`。
- 使用目录输入 Schema 对 `StructuredAgentCall.inputs` 做确定性校验。
- 按 `always`、`conditional`、`never` 返回需要确认或已授权状态。
- 在收到 P2.3 产出的 `ApprovedCapabilityDispatch` 时，校验能力代码、目录固定分发键和输入快照完全匹配。
- 将目录不可用、能力不可用、输入无效、提议不匹配等分支映射为稳定错误码，且不产生任何执行副作用。

**Non-Goals:**

- 不消费 `PendingProposalStorePort`，不解析用户自然语言，不创建确认提议。
- 不调用 `ControlledDispatcher`、Agent Runtime、LLM、Provider 或业务 Use Case。
- 不新增 HTTP、数据库、Redis、Conversation 事件或前端交互。
- 不实现 `never` 能力的实际执行；P2.6 决定授权结果如何进入受控分发。

## Decisions

### 1. 使用独立的策略校验应用服务

新增 `AgentCallPolicyValidator`，输入为结构化调用、可信请求主体和可选的受信批准分发对象，输出为不可变策略结果。它依赖 `CapabilityCatalogPort`，复用现有输入校验函数，不修改旧 `IntentInteractionGateway`。

替代方案是在 `ControlledDispatcher` 中增加校验。这样会把“是否允许调用”和“如何执行调用”耦合，后续 Dialogue Runtime 无法在执行前展示确认状态，因此不采用。

### 2. 目录策略是唯一确认事实来源

校验服务每次从目录读取能力，不接受结构化调用或批准对象覆盖 `confirmation_policy`、权限、输入 Schema 或 `dispatch_key`。`conditional` 当前没有独立条件规则，按 `always` 处理；`never` 在目录、权限和输入通过后直接返回授权。

### 3. 批准提议只做严格匹配，不被视为目录事实

传入的 `ApprovedCapabilityDispatch` 只能来自确认层的受信应用边界。服务将其 `capability_code`、`dispatch_key` 和 `inputs` 与当前目录及 `StructuredAgentCall` 做精确比较；任何不匹配都返回拒绝。服务不消费提议、不验证提议 ID 的存储状态，也不执行目标能力，这些职责留在确认层和 P2.6。

### 4. 错误按安全边界归类

目录异常返回 `CAPABILITY_CATALOG_UNAVAILABLE`；目录没有可用 Agent 能力返回 `CAPABILITY_UNAVAILABLE`；非 Agent 条目返回 `CAPABILITY_TYPE_NOT_AGENT`；输入失败返回 `INPUT_VALIDATION_FAILED`；批准缺失返回 `CONFIRMATION_REQUIRED`；批准内容不匹配返回 `APPROVAL_MISMATCH`。返回消息不包含 Provider 异常、权限明细或输入原文。

## Risks / Trade-offs

- [目录在校验和后续分发之间发生变化] -> P2.6 必须再次读取目录并校验固定分发键；P2.5 的授权结果不是永久执行凭据。
- [调用方伪造批准对象] -> P2.5 只接受应用层对象，不开放 HTTP 适配；并严格匹配当前目录和调用输入，实际提议消费仍由确认层负责。
- [目录查询失败导致可用性下降] -> 显式返回不可用错误，不降级到调用对象或其他目录缓存。

## Migration Plan

无需数据迁移。新增服务和测试后由后续 P2.6、P3.1 逐步接入；V1 Gateway 与旧 HTTP 接口保持不变。回滚只移除新服务及其导出，不影响目录、确认提议或 Conversation 数据。

## Open Questions

无。跨请求确认恢复、授权结果持久化和异步执行状态留给后续 Dialogue/Task 变更。
