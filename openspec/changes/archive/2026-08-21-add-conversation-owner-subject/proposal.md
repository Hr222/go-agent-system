## Why

Conversation 当前只有 UUID，无法表达其归属主体。历史会话和上下文续写一旦对外开放，必须先以现有 `RequestPrincipal.subject` 建立稳定的 Mock 归属键。

## What Changes

- 为 Conversation 增加不可为空的 `owner_subject` 领域字段和 PostgreSQL 存储列。
- 新建 Conversation 时从可信主体写入归属；不接受客户端提交归属键。
- 为既有本地数据提供受控迁移策略。
- 不新增真实用户、认证协议或 HTTP 接口。

## Capabilities

### New Capabilities

- `conversation-owner-subject`: 定义 Conversation 的主体归属键、持久化和创建约束。

### Modified Capabilities

无。

## Impact

- 影响 Conversation 领域模型、ORM、SQL 迁移、mapper、创建服务与测试。
- 影响持久化；不影响 LLM Provider、HTTP 契约或前端。
- 使用已有静态/匿名主体作为 Mock，不新增用户数据或敏感信息。
