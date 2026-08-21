## ADDED Requirements

### Requirement: 当前主体可以列出自己的 Conversation 摘要

系统 MUST 通过 `GET /api/v1/conversations` 返回当前可信主体所属 Conversation 的最小摘要页。摘要 MUST 包含会话 UUID、创建时间和更新时间，并按最近更新时间倒序排列。

#### Scenario: 返回最近会话

- **WHEN** 当前主体拥有多个 Conversation
- **THEN** 系统只返回该主体的会话摘要
- **AND** 首页按 `updated_at` 从新到旧排列

#### Scenario: 稳定分页

- **WHEN** 当前主体使用上一页返回的游标请求后续列表
- **THEN** 系统返回后续摘要而不重复先前条目
- **AND** 同一更新时间的会话具有稳定顺序

### Requirement: 会话摘要不泄露消息事实

会话列表 MUST NOT 返回消息正文、ConversationEvent、附件、模型用量、权限或其他主体的会话。

#### Scenario: 空会话列表

- **WHEN** 当前主体没有 Conversation
- **THEN** 系统返回空摘要列表和无下一游标
