## ADDED Requirements

### Requirement: 普通 Interaction Chat 替换为上下文增强的既有运行时

系统 MUST 用上下文增强的既有流式 Conversation Runtime 替换已授权 `chat.general` 的 H1 流式运行时依赖。每个普通 Chat 请求 MUST 只进入这一条运行时链路，Interaction MUST NOT 自行读取或写入 Conversation、Message 或 ModelContext；需要确认的 Agent 请求 MUST 保持现有分支。

#### Scenario: 普通 Chat 进入 Dialogue

- **WHEN** Interaction 授权一个普通 `chat.general` 请求
- **THEN** 系统调用上下文增强的既有流式 Conversation Runtime
- **AND** 普通 Chat 不再调用无状态 StreamingChatApplication
- **AND** 普通 Chat 不再并行调用无上下文的流式 Conversation Runtime
- **AND** Agent 确认请求不进入普通 Dialogue 分支

### Requirement: SSE 元数据包含会话关联

普通 Chat 的首个 `meta` SSE 事件 MUST 包含 `request_id`、模型、Prompt 版本和由 Dialogue 确定的 `conversation_id`。系统 MUST NOT 在 SSE 中暴露历史文本、上下文成本、权限或 Provider 原始数据。

#### Scenario: 新会话开始输出

- **WHEN** 普通 Chat 已创建或解析 Conversation 并开始流式输出
- **THEN** 首个非心跳事件为包含有效 `conversation_id` 的 `meta`
- **AND** 后续 delta、complete、error 和心跳事件保持现有顺序与字段约束

### Requirement: Dialogue 失败映射为浏览器安全 SSE

系统 MUST 将 Conversation Access、上下文预算、流式 Provider 和持久化失败映射为受控 SSE 错误，不得暴露内部对象、堆栈、历史或主体信息。

#### Scenario: 上下文构建失败

- **WHEN** 流式 Dialogue 因上下文预算或会话访问失败而不能开始模型调用
- **THEN** Interaction 返回受控失败事件或响应
- **AND** 响应不包含内部上下文或访问校验细节
