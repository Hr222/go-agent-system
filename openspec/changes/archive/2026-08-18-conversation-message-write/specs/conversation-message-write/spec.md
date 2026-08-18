## ADDED Requirements

### Requirement: 系统可以创建空会话

系统 MUST 提供一个不依赖 HTTP 的应用能力创建 Conversation。每次成功创建 MUST 生成唯一 UUID，并持久化创建时间和更新时间；新会话不得自动产生 Message。

#### Scenario: 成功创建一个空会话

- **WHEN** 应用层执行创建会话用例
- **THEN** 系统 MUST 返回一个具有 UUID、创建时间和更新时间的 Conversation
- **AND** 数据库 MUST 保存该 Conversation
- **AND** 该会话的 Message 数量 MUST 为零

#### Scenario: 连续创建两个会话

- **WHEN** 应用层连续执行两次创建会话用例
- **THEN** 两次调用 MUST 返回不同的 Conversation UUID
- **AND** 两个会话 MUST 互不包含对方的消息

### Requirement: 系统可以按会话顺序追加消息

系统 MUST 向已存在的 Conversation 追加有效 Message。消息顺序号由系统按会话分配，第一条消息为 1，后续成功追加的消息依次递增；追加成功后 Conversation 的更新时间 MUST 被更新。

#### Scenario: 向空会话追加第一条消息

- **WHEN** 应用层向一个空会话追加有效角色和非空内容
- **THEN** 系统 MUST 持久化一条归属于该会话的 Message
- **AND** Message 的顺序号 MUST 为 1
- **AND** Message MUST 获得稳定的 UUID

#### Scenario: 向已有会话追加后续消息

- **WHEN** 一个会话已有顺序号为 1 的 Message，应用层再次追加有效消息
- **THEN** 新 Message 的顺序号 MUST 为 2
- **AND** 系统 MUST 保留第一条消息及其顺序号
- **AND** Conversation 的 `updated_at` MUST 晚于或等于追加前的值

#### Scenario: 追加消息保留有效内容

- **WHEN** 应用层追加首尾包含空格但去除首尾空白后仍非空的消息内容
- **THEN** 系统 MUST 接受该消息
- **AND** 持久化内容 MUST 保留调用方提交的原始文本

#### Scenario: 同一会话并发追加消息

- **WHEN** 两个并发写入请求同时向同一 Conversation 追加有效消息
- **THEN** 两次写入 MUST 都成功或明确失败
- **AND** 若两次都成功，两个 Message 的顺序号 MUST 唯一且分别为连续的 1、2
- **AND** 系统 MUST 不依赖调用方提供顺序号

### Requirement: 写入失败必须保持数据完整性

系统 MUST 拒绝不存在会话或不满足 Message 领域不变量的追加请求，并在失败后不留下新增的 Message 或部分更新的会话时间。

#### Scenario: 向不存在的会话追加消息

- **WHEN** 应用层使用不存在的 `conversation_id` 追加消息
- **THEN** 系统 MUST 返回明确的会话不存在错误
- **AND** 数据库 MUST 不保存该 Message

#### Scenario: 追加非法角色或空白内容

- **WHEN** 应用层使用不支持的角色或去除首尾空白后为空的内容追加消息
- **THEN** 系统 MUST 在写入前拒绝请求
- **AND** 已有消息 MUST 保持不变
- **AND** Conversation 的更新时间 MUST 不因失败写入而改变

#### Scenario: 数据库写入失败

- **WHEN** Message 写入或 Conversation 更新时间更新在事务中失败
- **THEN** 系统 MUST 回滚本次事务
- **AND** 数据库 MUST 不留下孤立 Message 或只更新一半的会话状态

### Requirement: Conversation 写入不改变现有外部接口

本能力 MUST 通过模块应用服务和端口提供，不得新增 Conversation HTTP 路由、前端调用、LLM 调用或 Agent 调用。

#### Scenario: 部署写入能力后访问 V1 单轮 Chat

- **WHEN** 仅部署 Conversation 写入能力并访问现有 `/api/v1/llm/chat`
- **THEN** 现有单轮 Chat 的行为和响应契约 MUST 保持不变
- **AND** 客户端 MUST 不需要提供 `conversation_id` 才能访问该旧接口
