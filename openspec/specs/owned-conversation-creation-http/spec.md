## Purpose

定义当前可信主体创建空 Conversation 的 HTTP 契约、安全边界和服务端标识生成规则，避免客户端伪造会话归属。

## Requirements

### Requirement: 当前主体可以创建空 Conversation

系统 MUST 通过 `POST /api/v1/conversations` 为当前可信主体创建一个空 Conversation，并返回其 UUID、创建时间和更新时间。请求体 MUST 不接受 `owner_subject`、消息、权限或模型参数。

#### Scenario: 创建空会话

- **WHEN** 有可用主体的调用方请求创建 Conversation
- **THEN** HTTP 返回 `201` 和新 Conversation 元数据
- **AND** Conversation 归属当前主体且不包含 Message

#### Scenario: 主体不可用

- **WHEN** 当前请求没有可用于持久化会话的可信主体
- **THEN** 系统返回受控拒绝
- **AND** 系统不创建 Conversation
