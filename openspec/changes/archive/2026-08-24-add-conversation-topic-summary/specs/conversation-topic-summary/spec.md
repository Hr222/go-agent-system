## ADDED Requirements

### Requirement: Conversation 可以保存首轮话题概括

系统 MUST 为 Conversation 保存可空、可编辑的 `topic_summary`。当会话尚无话题概括且首条有效 user Message 成功持久化后，系统 MUST 尝试生成不超过 80 个字符的单行话题概括；生成失败时 MUST 使用该消息的稳定截断文本回退，且不得阻塞本轮消息或模型回答的完成。

#### Scenario: 首轮消息生成话题概括

- **WHEN** 一个没有话题概括的 Conversation 成功保存首条 user Message
- **THEN** 系统保存一个非空的单行 `topic_summary`
- **AND** 会话列表可以读取该话题概括

#### Scenario: 话题概括生成失败

- **WHEN** 话题概括生成器失败或返回空结果
- **THEN** 系统使用首条 user Message 的稳定截断文本作为回退
- **AND** 本轮 user/assistant Message 持久化和流式回答不因话题概括失败而回滚

#### Scenario: 已有话题概括不被后续消息覆盖

- **WHEN** 一个已有话题概括的 Conversation 追加后续 user Message
- **THEN** 系统保留原话题概括

### Requirement: 当前主体可以修改自己的话题概括

系统 MUST 通过 `PATCH /api/v1/conversations/{conversation_id}/topic-summary` 允许当前主体设置或清除自己的 `topic_summary`。请求只接受话题概括字段；非空值 MUST 为单行且不超过 80 个字符，显式 `null` MUST 清除话题概括。

#### Scenario: 用户修改话题概括

- **WHEN** 当前主体提交有效的新话题概括
- **THEN** 系统更新该 Conversation 的话题概括并返回最新摘要

#### Scenario: 用户清除话题概括

- **WHEN** 当前主体提交 `topic_summary = null`
- **THEN** 系统清除该 Conversation 的话题概括
- **AND** 列表客户端可以使用日期回退显示

#### Scenario: 修改其他主体的会话

- **WHEN** 当前主体修改不属于自己的 Conversation
- **THEN** 系统返回受控拒绝
- **AND** 系统不修改目标会话
