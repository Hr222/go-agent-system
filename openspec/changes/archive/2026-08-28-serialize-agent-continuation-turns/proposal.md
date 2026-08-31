## Why

已确认的对话 Agent 调用会在同一 Conversation 内持久化 `agent_result`，随后读取历史、调用 continuation LLM 并写入 assistant Message。该路径目前没有加入普通流式 Chat 已使用的会话锁，因此普通 Chat 可以在 Agent 执行或 continuation 期间交错写入，造成上下文快照与最终消息顺序不确定。

需要把确认后的 Agent 完成过程纳入同一进程内既有的会话串行化边界，同时保留“等待用户确认时不阻塞会话”的现有交互。

## What Changes

- 将已确认的对话 Agent 调用接入进程共享的 `conversation_id` 协调器，并复用普通流式 Chat 的同一把会话锁。
- 对 `confirm` 动作，在消费一次性 proposal 与 pending invocation 前取得锁；锁覆盖 Tender Agent 执行、`agent_result` 或 `agent_error` 事实持久化、continuation 上下文构建、LLM 调用与 assistant Message 写入。
- 将确认后的 Agent 编排改为异步入口，以等待会话锁；保持 HTTP 响应字段、确认协议和 Agent 结果的既有对外外形。
- 保持待确认 proposal 不持锁；等待锁的确认请求被取消时不消费确认状态、不启动 Agent、不写入新的 Conversation 事实。
- 使用 Tender Agent 的受控替身补充与普通 Chat 的同会话时序、失败、取消及跨会话隔离测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `conversation-turn-serialization`: 将已确认的对话 Agent 完成过程纳入既有 Conversation 轮次互斥契约。

## Impact

- 影响 `InteractionChatStreamApplication` 的确认执行入口、交互 HTTP 确认路由、Composition Root 的协调器注入，以及对话 Agent invocation/continuation 的调用时序。
- 不新增 HTTP 字段、SSE 事件、数据库表、队列、Worker、Redis 或跨进程协调；不改变待确认 proposal 的用户交互。
- 已确认的同会话 Tender Agent 执行期间，后续普通 Chat 将等待至 Agent 结果与 continuation 的终态完成；不同 Conversation 仍不因会话锁彼此等待。
