## Why

P0.1 已经提供 Conversation/Message 的领域模型和 PostgreSQL 存储约束，但目前没有能够创建会话或追加消息的应用能力。若没有稳定的写入端口，多轮对话和后续历史读取只能直接操作 ORM，无法保证事务边界、消息顺序和错误行为一致。

## What Changes

- 新增 Conversation 写入应用能力，支持创建空会话和向已有会话追加一条消息。
- 新增 Conversation 写入 Port 与 PostgreSQL Repository，实现领域对象与持久化记录之间的事务性写入。
- 由服务端在会话级并发控制下分配下一个正整数消息顺序号，调用方不直接提交顺序号。
- 追加失败时保持事务原子性；不存在的会话、非法角色或空白内容必须明确失败且不产生孤立记录。
- 新增组合入口和应用、Repository、并发顺序及失败分支测试，但不新增 HTTP 路由。

## Capabilities

### New Capabilities

- `conversation-message-write`：创建 Conversation，并以事务和会话级顺序保证向已有会话追加消息。

### Modified Capabilities

- 无。

## Impact

- 影响 `app/modules/conversation/application` 与 `app/modules/conversation/ports`，增加写入用例和稳定端口。
- 影响 `app/infrastructure/persistence/repositories`，增加 PostgreSQL 写入实现；复用 P0.1 的 ORM、映射和约束，不新增表。
- 影响 `app/composition` 的依赖组装，使具体 Repository 只在 Composition Root 中实例化。
- 不修改现有 HTTP 契约、前端、LLM Provider、Interaction Gateway、Agent Runtime 或 `/api/v1/llm/chat`。
- 不引入 Redis、缓存、异步任务、Task Management、Turn、ConversationEvent 或 Harness；本 Change 只写入 P0.1 已定义的 Conversation 和 Message 记录。
