## MODIFIED Requirements

### Requirement: 普通 Chat SSE 返回 Conversation 标识

普通 Chat 的首个 `meta` SSE 事件 MUST 包含服务器确定的 `conversation_id`，并继续包含既有 request ID、模型和 Prompt 版本字段。系统 MUST 在收到首个上游活动后发送该事件；上游活动可以是可展示正文或内部 reasoning，但内部 reasoning 不得写入 SSE 内容。

#### Scenario: 新会话流式输出

- **WHEN** 普通 Chat 创建新 Conversation 后收到首个上游活动
- **THEN** 首个非心跳事件是含有效 `conversation_id` 的 `meta`
- **AND** 后续 delta、complete、error 和心跳字段保持浏览器安全
- **AND** reasoning 不作为 `delta` 内容发送
