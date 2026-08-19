## Context

当前系统已经有 Conversation、消息历史和基础 `BasicDialogueRuntime`，也有 P2.6 的 `AgentCallDispatcher`。Conversation 消息表只支持 `system/user/assistant` 文本，不能安全承载 Agent 的结构化结果；P2.6 的结果契约只在当前调用内存中返回，没有历史关联。

P3.1 只负责一次 Agent 调用和结果落盘。页面可以看到“需要确认、执行完成、执行失败”和受控结果摘要，但不要求 LLM 立即把结果改写成最终回答；这部分留给 P3.2。

## Goals / Non-Goals

**Goals:**

- 定义 Conversation 事件的最小 `agent_call`、`agent_result`、`agent_error` 事件契约。
- 在 Agent 执行前校验会话存在、调用关联标识和批准状态；只调用 P2.6 分发服务。
- 成功或失败后最多写入一个结果事件，事件包含可安全序列化的结构化载荷和关联 ID。
- 提供一个可供页面调用的 V2 Agent Invocation HTTP 入口，并返回浏览器安全的状态和结果摘要。
- 让 Tender Agent 的文件结果投影为文件名、媒体类型、大小和下载/资源引用等元数据，不把二进制内容写进事件表。

**Non-Goals:**

- 不生成最终 LLM 自然语言回答，不修改 `BasicDialogueRuntime` 的普通 Chat 行为；P3.2 负责 Agent Result 之后的续写。
- 不实现多 Agent、SubAgent、Workflow、Task Management、自动重试、断点恢复或并行执行。
- 不删除或替换旧 V1 HTTP、MCP 或 Interaction Gateway。
- 不把客户端提交的权限、分发键、执行器地址或批准对象当作授权事实。

## Decisions

### 1. Conversation 事件单独建表

新增 `conversation_event` 表，字段包括事件 ID、Conversation ID、事件类型、调用 ID、事件顺序、JSONB 载荷和创建时间。消息仍只保存用户和助手文本，事件负责保存 Agent 调用生命周期，避免把结构化对象伪装成自然语言消息。

替代方案是把 JSON 序列化后写入 assistant Message，但这会污染上下文、丢失事件类型和关联字段，也会让 P3.2 无法区分 Agent 结果和用户可见文本，因此不采用。

### 2. Dialogue Application 只消费 P2.6 的分发端口

新增 `DialogueAgentInvocationService`，输入包含 Conversation ID、结构化 `AgentCall`、可信主体和可选 `ApprovedCapabilityDispatch`。服务先确认会话存在，再调用 `AgentCallDispatcher`；未授权时写入受控失败/待确认事件，不触达 Agent Runtime。具体目录、权限和执行器仍由 P2.5/P2.6 负责。

### 3. 事件载荷采用白名单投影

成功事件保存调用关联字段、能力代码、结构化输出和可选的资源元数据；失败事件保存稳定错误码、安全消息和 `retryable`。对 Tender 结果只保留文件资源的元数据和服务端资源标识，禁止保存 `content` 原始字节、Provider 响应、权限集合和异常堆栈。

### 4. HTTP 入口创建或复用 Conversation

新增 V2 路由接受可选 `conversation_id`、用户可见请求文本、能力代码和业务输入。没有会话标识时创建新 Conversation；有会话标识时校验会话存在。HTTP 层只负责协议转换，服务端根据当前主体生成 `StructuredAgentCall` 和调用关联 ID，不能让浏览器填写 `dispatch_key` 或权限。

### 5. 页面先展示事件结果，不提前做 P3.2 续写

前端使用新的 V2 Agent 调用 API 展示确认状态、执行状态、错误消息和文件结果元数据。原有普通 Chat 流保持不变；P3.2 接入后再把 `agent_result` 交给 LLM 生成最终助手消息。

## Risks / Trade-offs

- [事件写入成功但 HTTP 响应中断] -> 事件带有唯一 `call_id`，后续历史读取可以恢复结果；本 Change 不做自动重试。
- [Agent 结果包含不可序列化对象或二进制] -> 使用白名单 JSON 投影，非法结果写入 `AGENT_OUTPUT_INVALID`，Tender 文件只允许元数据。
- [重复请求导致重复执行] -> 当前只保证单次命令内最多一次执行；幂等键和恢复由后续 Task/Dialogue Change 决定，并在 API 中返回 `call_id` 供上层追踪。
- [事件表与消息表事务边界不同] -> 每次结果事件独立提交；P3.2 读取事件时按事件顺序和调用 ID 关联，不把未完成消息伪造成助手回答。

## Migration Plan

先增加事件领域模型、端口、ORM 模型和 `sql/008_conversation_event.sql`，再实现应用服务和 HTTP/前端适配。部署前执行幂等 SQL；回滚时停止 V2 路由并保留事件表，不影响旧消息和 V1 接口。归档前运行后端全量测试、前端测试、Ruff、TypeScript 构建和 OpenSpec 严格校验。

## Open Questions

无。事件到最终助手消息的上下文映射、事件压缩和重试策略留给 P3.2 及后续 Change。
