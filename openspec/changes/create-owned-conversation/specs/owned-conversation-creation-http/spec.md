## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Conversation 写入不新增独立外部接口

消息追加能力 MUST 通过模块应用服务和 Port 提供，不得新增独立的 Message 写入 HTTP、前端、LLM 或 Agent 调用。系统可以通过受主体范围保护的 `POST /api/v1/conversations` 创建空 Conversation；该接口不得追加 Message、调用 LLM 或 Agent。

#### Scenario: 部署会话写入与创建能力后访问统一对话入口

- **WHEN** 部署 Conversation 写入和受主体范围保护的创建接口，并访问 `/api/v1/interaction/chat/stream`
- **THEN** 统一入口现有行为保持不变
- **AND** 系统不新增独立的 Message 写入 HTTP 路由
