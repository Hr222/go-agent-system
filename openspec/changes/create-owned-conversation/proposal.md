## Why

前端“新建对话”需要在发送第一条消息前取得可归属、可上传附件的会话 ID。已有创建能力只在应用层可用，尚未提供受主体范围约束的 HTTP 契约。

## What Changes

- 新增创建当前主体 Conversation 的 HTTP 接口和浏览器安全响应模型。
- 接口仅创建空会话，不调用 LLM、不追加消息、不创建 Agent 调用。
- 复用 Conversation Access，拒绝没有可用主体的创建请求。

## Capabilities

### New Capabilities

- `owned-conversation-creation-http`: 定义当前主体创建空 Conversation 的 HTTP 行为。

### Modified Capabilities

- `conversation-message-write`: 允许受主体范围保护的独立会话创建 HTTP 接口，同时保留消息追加不暴露独立写接口的限制。

## Impact

- 影响 HTTP route/schema/assembler、Composition Root 与前端 API；不新增数据库表或 LLM 调用。
