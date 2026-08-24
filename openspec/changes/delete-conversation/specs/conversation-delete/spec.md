## ADDED Requirements

### Requirement: 当前主体可以真实删除自己的会话

系统 MUST 提供 `DELETE /api/v1/conversations/{conversation_id}`，只允许当前可信主体删除自己拥有的 Conversation。成功时 MUST 返回 `204`，并通过数据库级联删除该会话的消息和 ConversationEvent；删除失败时 MUST 回滚，不留下部分删除状态。

#### Scenario: 删除自己的会话及级联事实

- **WHEN** 当前主体请求删除自己拥有且包含消息、事件的会话
- **THEN** HTTP 返回 `204`
- **AND** Conversation、关联消息和事件均从数据库中消失

#### Scenario: 删除其他主体的会话

- **WHEN** 当前主体请求删除不属于自己的会话
- **THEN** HTTP 返回统一的会话不可用响应
- **AND** 目标会话及其消息、事件保持不变

#### Scenario: 匿名删除

- **WHEN** 未提供可信主体的调用方请求删除会话
- **THEN** 系统返回受控拒绝
- **AND** 不执行数据库删除

#### Scenario: 无效或不存在的会话标识

- **WHEN** 请求包含无效 UUID 或不存在的会话 UUID
- **THEN** 系统返回受控拒绝
- **AND** 不改变任何持久化数据

#### Scenario: 数据库删除失败

- **WHEN** 删除事务提交时发生数据库异常
- **THEN** 系统回滚删除事务
- **AND** Conversation、消息和事件仍然存在
