# llm-chat Specification

## Purpose
定义独立 LLM 单轮对话的 HTTP、Application 和前端可观察行为。

当前能力不包含会话历史、上下文记忆、流式输出、工具调用、知识库引用或 Agent 编排。
## Requirements
### Requirement: The system provides a single-turn LLM chat contract

The system SHALL 通过 `POST /api/v1/llm/chat` 接收一条用户消息，并返回模型回答、模型标识、Prompt 版本和可选的 Token 使用信息。

#### Scenario: A valid message returns a single-turn response

- **WHEN** 客户端提交长度在允许范围内且包含非空内容的 `message`
- **THEN** 系统调用一次 Chat Application
- **AND** 返回 `answer`、`model`、`prompt_version` 和 `usage` 字段
- **AND** 响应不包含会话历史、工具调用或知识库引用

#### Scenario: A message longer than the contract limit is rejected

- **WHEN** 客户端提交超过 10,000 个字符的 `message`
- **THEN** HTTP 接口返回 `422`
- **AND** 系统不调用 LLM Application

### Requirement: The system validates and normalizes chat input

The system MUST 拒绝空消息，并在 Application 层去除消息首尾空白后再调用 LLM Port。

#### Scenario: An empty message is rejected by the HTTP contract

- **WHEN** 客户端提交空字符串作为 `message`
- **THEN** HTTP 接口返回 `422`

#### Scenario: A whitespace-only message is rejected by the application

- **WHEN** 客户端提交只包含空白字符的 `message`
- **THEN** HTTP 接口返回 `400`
- **AND** 系统不调用 LLM Port

### Requirement: The system maps LLM availability and response failures

The system SHALL 将配置缺失、上游调用失败和空模型响应转换为稳定的 HTTP 错误状态。

#### Scenario: The LLM service is not configured

- **WHEN** Chat Application 抛出 `ServiceNotConfiguredError`
- **THEN** HTTP 接口返回 `503`
- **AND** 响应包含可理解的错误原因

#### Scenario: The upstream model call fails

- **WHEN** Chat Application 抛出 `UpstreamServiceError`
- **THEN** HTTP 接口返回 `502`
- **AND** 响应包含可理解的错误原因

#### Scenario: The model returns an empty response

- **WHEN** LLM Port 返回空内容
- **THEN** Chat Application 将其视为失败
- **AND** HTTP 接口返回 `502`

### Requirement: The frontend presents the single-turn chat lifecycle

The frontend MUST 通过统一 Axios Client 调用 LLM API，并向用户展示单轮请求的加载、成功、失败和重试状态。

#### Scenario: The user sends a valid message

- **WHEN** 用户输入非空消息并发送
- **THEN** 页面展示用户消息和模型回答
- **AND** 展示模型标识、请求耗时和可用的 Token 信息

#### Scenario: The request is in progress

- **WHEN** LLM 请求尚未完成
- **THEN** 页面展示正在请求模型的状态
- **AND** 禁止重复发送同一时刻的请求

#### Scenario: The request fails and the user retries

- **WHEN** LLM 请求失败
- **THEN** 页面展示错误信息和重试入口
- **AND** 重试使用原始失败请求内容

#### Scenario: The current chat does not promise unsupported capabilities

- **WHEN** 用户查看当前 Chat 页面
- **THEN** 页面明确当前为单轮模型调用验证
- **AND** 不宣称支持会话历史、上下文记忆、流式输出、工具调用或 RAG 问答
