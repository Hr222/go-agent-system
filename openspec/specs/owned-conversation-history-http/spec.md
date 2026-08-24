## Purpose

定义当前主体读取指定 Conversation 消息历史的 HTTP 契约、分页行为和响应安全边界。

## Requirements

### Requirement: 当前主体可以分页读取自己的会话消息

系统 MUST 通过 `GET /api/v1/conversations/{conversation_id}/messages` 返回当前主体已准入 Conversation 的元数据和消息页。消息 MUST 按 `sequence` 升序，响应 MUST 包含 `has_more` 与 `next_after_sequence`。

#### Scenario: 读取会话第一页

- **WHEN** 当前主体请求自己的多消息 Conversation 且未提供游标
- **THEN** 系统返回按顺序排列的浏览器安全消息页
- **AND** 响应包含会话元数据和下一游标信息

#### Scenario: 继续读取下一页

- **WHEN** 当前主体使用上页 `next_after_sequence` 请求同一会话
- **THEN** 系统只返回顺序号更大的消息
- **AND** 响应不重复前页消息

### Requirement: 历史 HTTP 查询保持主体隔离和只读

系统 MUST 在读取前完成 Conversation Access 校验。响应 MUST NOT 包含 ConversationEvent、附件原始内容、ModelContext、权限或 Provider 数据；该查询不得修改 Conversation 或 Message。

#### Scenario: 读取其他主体会话

- **WHEN** 当前主体请求不属于自己的 Conversation
- **THEN** 系统返回受控拒绝
- **AND** 系统不返回任何会话或消息字段
