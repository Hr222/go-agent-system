# Attachment Access Binding

## Purpose

Define subject, conversation, and lifecycle controls for server-managed attachments.

## Requirements

### Requirement: 附件访问主体绑定

系统 MUST 将附件绑定到创建主体和可选会话，并在读取、消费和删除时重新校验绑定。创建附件的访问上下文 MUST 包含非空的可信主体标识；系统 MUST 拒绝缺少主体标识的创建请求。

#### Scenario: 所有者读取

- **WHEN** 创建主体在有效期内读取自己的附件
- **THEN** 系统返回附件元数据和内容

#### Scenario: 其他主体读取

- **WHEN** 不同主体使用同一附件 ID 读取
- **THEN** 系统拒绝请求
- **AND** 不泄漏附件是否存在以外的敏感内容

#### Scenario: 会话不匹配

- **WHEN** 主体相同但会话绑定不匹配
- **THEN** 系统拒绝读取或消费

#### Scenario: 匿名主体尝试创建附件

- **WHEN** 附件创建上下文没有可信主体标识
- **THEN** 系统拒绝创建
- **AND** 系统不返回可用于后续读取或消费的附件引用

### Requirement: 附件生命周期状态

系统 MUST 支持过期和一次性消费状态，并在终态禁止再次读取。

#### Scenario: 一次性消费

- **WHEN** 合法主体成功消费一次性附件
- **THEN** 附件进入 consumed 状态
- **AND** 后续消费失败

#### Scenario: 过期消费

- **WHEN** 附件已超过 TTL
- **THEN** 系统返回过期错误
- **AND** 不读取文件内容
