# conversation-history-read Specification

## Purpose
TBD - created by archiving change conversation-history-read. Update Purpose after archive.
## Requirements
### Requirement: 系统可以读取会话及有序消息历史

系统 MUST 为已存在的 Conversation 返回会话元数据和消息历史页。消息 MUST 按 `sequence` 从小到大返回，且领域对象中的 UUID、角色、内容和顺序号 MUST 与持久化记录一致。

#### Scenario: 读取包含多条消息的会话

- **WHEN** 应用层读取一个已有多条消息的 Conversation
- **THEN** 系统 MUST 返回该会话的 UUID、创建时间和更新时间
- **AND** 消息 MUST 按 `sequence` 升序返回
- **AND** 每条消息 MUST 保留其 UUID、角色、原始内容和顺序号

#### Scenario: 读取空会话

- **WHEN** 应用层读取一个已存在但没有消息的 Conversation
- **THEN** 系统 MUST 返回该会话元数据
- **AND** 消息列表 MUST 为空
- **AND** 系统 MUST 返回 `has_more = false` 且没有下一游标

#### Scenario: 读取不存在的会话

- **WHEN** 应用层使用不存在的 `conversation_id` 读取历史
- **THEN** 系统 MUST 返回明确的会话不存在错误
- **AND** 系统 MUST 不把该情况伪装为空会话

### Requirement: 历史读取支持按顺序游标分页

系统 MUST 支持使用 `limit` 和可选的 `after_sequence` 读取消息窗口。`limit` 默认 MUST 为 50，允许范围 MUST 为 1 到 200；`after_sequence` 存在时，只能返回顺序号大于该值的消息。

#### Scenario: 读取第一页并返回下一游标

- **WHEN** 一个会话有 3 条消息且使用 `limit = 2`、不提供 `after_sequence`
- **THEN** 系统 MUST 返回顺序号为 1、2 的消息
- **AND** `has_more` MUST 为 true
- **AND** 下一游标 MUST 指向顺序号 2

#### Scenario: 使用下一游标读取后续页

- **WHEN** 调用方使用上一页返回的游标继续读取同一会话
- **THEN** 系统 MUST 只返回顺序号大于该游标的消息
- **AND** 返回结果 MUST 不重复上一页消息
- **AND** 没有更多消息时 `has_more` MUST 为 false 且没有下一游标

#### Scenario: 分页参数无效

- **WHEN** 调用方提供小于 1 或大于 200 的 `limit`，或提供非正的 `after_sequence`
- **THEN** 应用层 MUST 拒绝请求
- **AND** 数据库 MUST 不执行历史写入

### Requirement: 历史读取保持只读和模块边界

历史读取 MUST 只通过 Conversation 读取应用服务和 Port 查询，不得修改 Conversation/Message，不得新增 HTTP、前端、LLM 或 Agent 调用。

#### Scenario: 历史读取期间追加新消息

- **WHEN** 读取一页历史的同时另一个请求向同一会话追加消息
- **THEN** 已返回页面 MUST 保持 `sequence` 升序
- **AND** 调用方可以使用返回游标继续读取之后的消息
- **AND** 历史读取 MUST 不阻塞或修改追加事务

#### Scenario: 部署读取能力后访问统一对话入口

- **WHEN** 仅部署 Conversation 历史读取能力并访问 `/api/v1/interaction/chat/stream`
- **THEN** 统一入口的识别、授权和确认边界 MUST 保持不变
- **AND** 系统 MUST 不新增 Conversation HTTP 路由
