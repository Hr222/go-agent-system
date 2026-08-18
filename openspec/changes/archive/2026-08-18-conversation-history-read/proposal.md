## Why

P0.1 和 P0.2 已经建立会话存储与写入能力，但上层还无法稳定恢复会话元数据和有序消息。没有独立的读取端口，后续 Context Builder 只能直接查询数据库，难以复用分页边界和缺失会话错误。

## What Changes

- 新增 Conversation 历史读取应用能力，返回会话元数据和按 `sequence` 升序排列的消息页。
- 新增基于 `after_sequence` 的游标分页，返回 `has_more` 与下一游标，支持大历史分段读取。
- 新增 Conversation 读取 Port、PostgreSQL Repository 和 Composition Root 组装入口。
- 对分页大小、游标和不存在会话进行应用层校验；读取失败不修改会话或消息数据。
- 新增读取、分页、空历史、缺失会话、架构边界和 V1 回归测试，但不新增 HTTP 路由。

## Capabilities

### New Capabilities

- `conversation-history-read`：读取会话元数据和按消息顺序分页的历史记录。

### Modified Capabilities

- 无。

## Impact

- 影响 `app/modules/conversation/application` 与 `app/modules/conversation/ports`，增加历史读取结果契约和应用服务。
- 影响 `app/infrastructure/persistence/repositories`，增加只读 PostgreSQL 查询适配器；复用 P0.1 ORM、映射和 P0.2 的缺失会话错误。
- 影响 `app/composition` 的 Conversation 组装入口；不新增数据库表、迁移或 Redis。
- 不修改 HTTP 契约、前端、LLM Provider、Dialogue Runtime、Context Builder、Interaction Gateway、Agent Runtime 或 `/api/v1/llm/chat`。
