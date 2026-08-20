# Attachment Access Binding

## Purpose

Define subject, conversation, and lifecycle controls for server-managed attachments.

## Requirements

### Requirement: 附件访问主体绑定

系统 MUST 将附件绑定到创建主体和可选会话，并在读取、消费和删除时重新校验绑定。

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
