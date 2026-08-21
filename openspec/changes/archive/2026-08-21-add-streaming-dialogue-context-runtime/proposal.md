## Why

同步 `BasicDialogueRuntime` 已能从 Conversation 历史构建 `ModelContext`，但普通 Chat 使用的是流式模型端口。需要先在 Dialogue 层补齐可测试的流式上下文运行时，再由 Interaction 将其接入浏览器入口。

## What Changes

- 扩展已完成的流式 Conversation Runtime：保留其创建或解析已准入会话、写 user Message、调用流式 LLM、完成后写 assistant Message 的单一事实链路，并在请求构造前补入 `ModelContext`。
- 在请求内累积流式内容，失败、取消、断开或空回答时不写入 assistant Message。
- 保持 `ModelContext -> ChatLlmRequest` 的模型无关映射，不增加 HTTP/SSE 或前端行为。

## Capabilities

### New Capabilities

- `streaming-dialogue-context-runtime`: 定义既有流式 Conversation Runtime 的上下文构建扩展及其模型请求映射。

### Modified Capabilities

无。

## Impact

- 影响 Dialogue、Conversation、Streaming LLM Port、Composition Root 与后端测试；不新增 HTTP 路由或 Provider 私有状态。
