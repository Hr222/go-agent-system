## Context

当前 `interaction` 已有 `IntentAssessment`、`ConfirmationProposal` 和 `ApprovedCapabilityDispatch`。这些对象服务于 V1 统一入口或确认流程：前者表达识别结果，后两者包含确认提议和旧 Dispatcher 所需的分发信息，不能直接作为 V2 Dialogue Runtime 与 Agent Runtime 之间的稳定协议。

P2.4 只建立结构化 Agent Call 的领域契约。它必须能让上层记录“哪一次对话中的哪一次调用请求了哪个目录能力”，也必须能让未来 Agent Runtime 返回成功或受控失败，而不把执行器、权限、Provider 或 HTTP 协议泄漏到领域层。

## Goals / Non-Goals

**Goals:**

- 定义 `StructuredAgentCall`、`AgentCallResult` 和 `AgentCallError` 三个可序列化、可校验的领域模型。
- 在请求、成功结果和失败结果之间保留 `call_id`、`capability_code` 以及可选的 `conversation_id`、`turn_id`、`run_id`、`parent_run_id` 关联信息。
- 通过拒绝未知字段、禁止空标识和受控错误字段，阻止调用对象携带分发键、权限、确认状态、URL、函数引用或 Provider 对象。
- 让后续 Gateway、Agent Runtime、Conversation 事件和 HTTP/Agent 适配器可以复用同一内部契约。

**Non-Goals:**

- 不实现能力目录查找、输入 Schema 复核、权限校验、用户确认或 Agent 分发。
- 不调用 LLM、Agent、MCP、Function Calling 或任何 Provider。
- 不新增 HTTP、数据库、Redis、Conversation 持久化或前端协议。
- 不替换现有 `IntentAssessment`、`ConfirmationProposal` 或 `ApprovedCapabilityDispatch`；迁移由后续 Change 负责。

## Decisions

### 1. 将调用契约放在 `interaction` 领域层

`StructuredAgentCall` 是 LLM、Interaction Gateway 和 Agent Runtime 之间的共享业务边界，不属于 LLM Provider，也不属于某个 Tender Agent。放在 `app/modules/interaction/domain` 可以让后续调用方依赖领域契约，而不依赖 HTTP Schema 或 SDK 类型。

替代方案是放入 `modules/llm`，但这样会把业务能力代码和模型调用能力绑定；放入 `modules/agent` 则会让普通 Agent 能力成为契约所有者，均不符合 V2 的同级模块边界。

### 2. 请求与结果使用三种拒绝未知字段的不可变 Pydantic 模型

契约使用 `ConfigDict(extra="forbid", frozen=True)`。调用方只能提交声明字段，模型创建后不能替换顶层字段；嵌套输入和输出在构造时复制为 JSON 对象。标识字段必须是非空字符串，`inputs` 和 `output` 必须是对象，失败结果使用受控 `error_code`、用户可安全展示的 `message` 和 `retryable` 标志。

替代方案是使用 `dict[str, object]` 或复用 HTTP Schema。前者无法在跨层边界阻止拼写错误和敏感执行字段，后者会让领域层依赖传输协议，因此不采用。

### 3. 契约不保存执行授权信息

请求只保存稳定的 `capability_code` 和业务输入，不保存目录 `dispatch_key`、权限集合、确认状态、工具地址、类名、函数名或执行器实例。成功结果只保存业务输出；失败结果只保存安全错误码、消息和是否可重试。Gateway 后续必须根据目录重新校验，不能把模型产生的对象直接视为执行授权。

### 4. 关联 ID 采用可选字段而非强制依赖 Conversation

`conversation_id`、`turn_id`、`run_id` 和 `parent_run_id` 允许为空，使 P2.4 可被当前独立交互或 Agent 适配器使用；Dialogue Runtime 接入后可以填充这些 ID，并据此写入 Conversation 事件。P2.4 不引入 Conversation Repository，也不规定 ID 的生成或持久化方式。

## Risks / Trade-offs

- [模型输出或 Agent 输出包含非 JSON 对象] -> Pydantic 在契约入口拒绝无法转换为声明对象的数据，适配器负责先做协议转换。
- [冻结模型不能阻止嵌套字典被原地修改] -> 契约边界只暴露模型值；后续状态存储或跨请求传递时使用 `model_copy(deep=True)`，与现有提议存储保持同一快照原则。
- [错误信息仍可能被调用方写入敏感内容] -> 契约只提供受控 `error_code`、短消息和布尔重试标志；Provider 异常堆栈、请求体和凭据不得写入该对象，具体适配器负责脱敏。

## Migration Plan

无需数据迁移或部署顺序调整。先新增领域模型和单元测试，再由后续 P2.5/P2.6 在新 Dialogue 链路中逐步消费。现有 V1 链路继续使用旧对象，回滚时删除新增导出和测试即可，不影响数据库、Conversation 或外部 API。

## Open Questions

无。Agent 输出的具体业务 Schema、超时、重试次数和执行状态机留给 Agent Runtime 与目录策略的后续 Change。
