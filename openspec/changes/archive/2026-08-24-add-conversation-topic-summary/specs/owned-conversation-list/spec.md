## MODIFIED Requirements

### Requirement: 当前主体可以列出自己的 Conversation 摘要

系统 MUST 通过 `GET /api/v1/conversations` 返回当前可信主体所属 Conversation 的最小摘要页。摘要 MUST 包含会话 UUID、创建时间、更新时间和可空的 `topic_summary`，并按最近更新时间倒序排列。

#### Scenario: 返回最近会话

- **WHEN** 当前主体拥有多个 Conversation
- **THEN** 系统只返回该主体的会话摘要
- **AND** 首页按 `updated_at` 从新到旧排列

#### Scenario: 稳定分页

- **WHEN** 当前主体使用上一页返回的游标请求后续列表
- **THEN** 系统返回后续摘要而不重复先前条目
- **AND** 同一更新时间的会话具有稳定顺序

#### Scenario: 摘要包含话题概括

- **WHEN** 会话已经生成或设置话题概括
- **THEN** 列表项返回该 `topic_summary`
- **AND** 列表不返回消息正文或完整历史
