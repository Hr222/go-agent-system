## ADDED Requirements

### Requirement: Conversation Access 按可信主体解析会话

系统 MUST 使用可信 `RequestPrincipal.subject` 与 `conversation_id` 一起解析已有 Conversation。主体可以创建新的已归属 Conversation；主体缺失时系统 MUST 拒绝持久化会话访问。

#### Scenario: 主体访问自己的会话

- **WHEN** 可信主体请求其 `owner_subject` 匹配的 Conversation
- **THEN** 系统返回该会话供后续读取或写入
- **AND** 查询条件同时包含主体和会话标识

#### Scenario: 主体创建新会话

- **WHEN** 可信主体请求创建 Conversation
- **THEN** 系统创建归属该主体的空 Conversation
- **AND** 返回的 Conversation 不包含自动生成的 Message

### Requirement: 未准入会话不能泄露事实

系统 MUST 对不存在、非 owner 或主体缺失的会话访问返回同一受控拒绝类别。拒绝路径 MUST NOT 读取消息、事件或附件，不得追加 Message 或调用模型。

#### Scenario: 主体访问其他主体会话

- **WHEN** 主体提供属于另一主体的 `conversation_id`
- **THEN** 系统拒绝访问而不区分该会话是否存在
- **AND** 系统不返回会话元数据、消息或事件
