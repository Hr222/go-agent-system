## Context

现有 Chat 页面已经通过 `IntentInteractionGateway` 识别自然语言意图并显示确认卡片，但该网关的 `confirm()` 会直接调用通用 `ControlledDispatcher`。同时，已归档的 P3.1 又增加了独立 Agent 调用页面和 `/dialogue/agent-invocations` 接口，允许浏览器直接传入能力代码和输入。这两条链路并存，使 Agent 调用脱离了正常对话和统一识别边界。

Conversation 已具备消息、历史和 `agent_call`、`agent_result`、`agent_error` 事件；`DialogueAgentInvocationService` 已能在调用前写入待确认事件，并通过 P2.6 的 `AgentCallDispatcher` 执行一次已批准的 Agent 调用。数据库仍以 PostgreSQL 为事实存储，本次不引入 Redis。

## Goals / Non-Goals

**Goals:**

- 让用户在 Chat 中只提交自然语言，由 Gateway 识别 Agent 意图并创建确认提议。
- 将确认提议与 Conversation 的 `agent_call` 事件关联；确认或取消都写入对应的终态事件。
- 将“消费确认提议”和“执行 Agent”拆开：Gateway 负责前者，Dialogue 应用服务负责后者。
- 删除能让浏览器直传能力代码的独立 Agent 调用入口。

**Non-Goals:**

- 不让 Agent 结果自动触发 LLM 续写；该能力属于 P3.2。
- 不改造非 Agent 的既有交互确认与直接分发行为。
- 不实现多 Agent、SubAgent、Workflow、任务管理、持久化确认提议或自动重试。
- 不改变 V1 `/api/v1/llm/chat` 的兼容范围。

## Decisions

### 1. Agent 确认仍回到 Gateway，但使用只消费确认的应用契约

为 `IntentInteractionGateway` 增加一个专供对话 Agent 使用的确认方法。它原子消费按主体绑定的提议、使用现有 `ExplicitCapabilityConfirmation` 重新校验，并在确认成功时返回服务端构造的 `ApprovedCapabilityDispatch`；它不调用 `ControlledDispatcher`。

`confirm()` 保持给既有非 Agent HTTP 调用方使用，继续执行原有受控分发。这样不扩大本 Change 的回归面，同时 Dialogue 链路不再让 Gateway 绕开 Conversation 事件。

替代方案是先调用旧 `confirm()`，再由 Dialogue 记录结果。该方案无法确保 Agent 结果只经 P2.6 Dispatcher 一次，也会让 `agent_call` 事件晚于执行发生，因此不采用。

### 2. Chat 流在识别到 Agent 待确认后创建并绑定调用上下文

`InteractionChatStreamApplication` 接受 `DialogueAgentInvocationService` 和短期的“对话 Agent 待确认”存储。Chat 可以提交文本与上传文件的服务端引用等原始上下文，但不能提交能力代码、分发键或批准对象。Gateway 返回 Agent 的待确认提议时，应用服务创建或复用 Conversation、追加用户消息、写入 `agent_call` 的 `confirmation_required` 事件，并把 Conversation、结构化调用和 Gateway 提议标识按当前主体短期绑定。SSE 的 `approval_required` 事件带回 `conversation_id` 与安全确认摘要。

确认接口根据 `proposal_id` 读取绑定上下文，而不是接受 `call_id`、能力代码或输入；它先通过 Gateway 只消费确认，再将批准对象交给 `DialogueAgentInvocationService`。取消同样先消费提议，再记录取消事件。失败时只返回稳定错误与安全消息。

替代方案是把 `StructuredAgentCall`、批准对象或能力代码交给浏览器在确认时回传。浏览器数据不能作为授权事实，也容易被篡改，因此不采用。

### 3. 正常 Chat 保持现有 SSE 交互模型，Agent 结果以受控摘要结束本轮

Chat 页面沿用现有确认卡片。待确认 SSE 包含 `conversation_id`；页面把它作为当前会话标识。确认成功后，HTTP 返回 `DialogueAgentInvocationResult` 的安全投影，页面显示完成、失败或取消状态和结果摘要，而不把任意原始对象写入助手文本。

为了让旧前端确认 Hook 不必承担两套协议，确认接口保持 `InteractionGatewayResponse` 的外形，并仅为 Agent 结果补充浏览器安全的 `execution_result` 摘要。P3.2 接入后才把摘要放进 Context Builder 并生成最终 assistant Message。

### 4. 移除直达入口而不是保留隐藏兼容路径

删除 `/dialogue/agent-invocations` 和 `/dialogue/agent-invocations/{call_id}/confirmation`、相应 schema、依赖项、前端 API/Hook/页面、路由和导航项。没有重定向或废弃别名，避免出现可绕过 Gateway 的后门。

## Risks / Trade-offs

- [确认提议存储仍是进程内且有 TTL，服务重启后确认不可用] -> 本 Change 返回稳定的提议不可用错误；持久化确认与恢复另立 Change。
- [识别到 Agent 后创建 Conversation 但用户不确认] -> 保留待确认 `agent_call`，取消时写入取消终态；过期提议暂不补写终态，由后续恢复策略处理。
- [Chat 的非 Agent 确认路径被误接入 Dialogue] -> 仅当目录条目类型为 `agent` 且 Gateway 处于 `pending` 时创建对话 Agent 上下文；其他能力保留既有路径。
- [结果摘要在 P3.2 前不够像自然对话] -> 页面明确显示执行状态和受控摘要，不伪造 LLM 回复。

## Migration Plan

部署顺序是先增加 Gateway 只消费确认契约、Chat 对话适配和测试，再删除独立路由与前端入口。无数据库迁移。回滚时恢复上一版应用即可；已存在的 Conversation 事件不受影响，但已创建的进程内待确认提议会随重启失效。

## Open Questions

无。对话持久化历史的完整加载、Agent 结果续写和跨进程待确认恢复均留给后续 Change。
