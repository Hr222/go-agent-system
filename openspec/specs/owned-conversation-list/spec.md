## Purpose

提供当前可信主体所属 Conversation 的轻量摘要发现能力，支持稳定分页并避免泄露会话事实。

## Requirements

### Requirement: 当前主体可以列出自己的 Conversation 摘要

系统 MUST 通过 `GET /api/v1/conversations` 返回当前可信主体所属 Conversation 的最小摘要页。摘要 MUST 包含会话 UUID、创建时间、更新时间、可空的 `topic_summary` 和 `is_pinned`，并按置顶优先、最近更新时间倒序排列。

#### Scenario: 返回最近会话

- **WHEN** 当前主体拥有多个 Conversation
- **THEN** 系统只返回该主体的会话摘要
- **AND** 置顶会话先于未置顶会话
- **AND** 同一置顶状态内按 `updated_at` 从新到旧排列

#### Scenario: 稳定分页

- **WHEN** 当前主体使用上一页返回的游标请求后续列表
- **THEN** 系统返回后续摘要而不重复先前条目
- **AND** 置顶状态、同一更新时间的会话具有稳定顺序

#### Scenario: 摘要包含话题概括和置顶状态

- **WHEN** 会话已经生成或设置话题概括，或被当前主体置顶
- **THEN** 列表项返回对应的 `topic_summary` 和 `is_pinned`
- **AND** 列表不返回消息正文或完整历史

#### Scenario: 置顶整理不改变最近活动时间

- **WHEN** 当前主体置顶或取消置顶一个会话
- **THEN** 后续摘要返回该会话原有的 `updated_at`
- **AND** 会话只因 `is_pinned` 分组变化而改变列表位置

### Requirement: 会话摘要不泄露消息事实

会话列表 MUST NOT 返回消息正文、ConversationEvent、附件、模型用量、权限或其他主体的会话。

#### Scenario: 空会话列表

- **WHEN** 当前主体没有 Conversation
- **THEN** 系统返回空摘要列表和无下一游标
