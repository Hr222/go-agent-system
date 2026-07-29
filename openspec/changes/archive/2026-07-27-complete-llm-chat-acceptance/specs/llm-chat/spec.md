## ADDED Requirements

### Requirement: 系统提供独立的单轮 LLM 对话契约

系统必须（MUST）通过 `POST /api/v1/llm/chat` 接收一条用户消息，并返回模型回答、模型标识、Prompt 版本和可选的 Token 使用信息。

#### Scenario: 有效消息返回单轮响应

- **WHEN** 客户端提交长度在允许范围内且包含非空内容的 `message`
- **THEN** 系统调用一次 Chat Application
- **AND** 返回 `answer`、`model`、`prompt_version` 和 `usage` 字段
- **AND** 响应不包含会话历史、工具调用或知识库引用

#### Scenario: 超过契约长度限制的消息被拒绝

- **WHEN** 客户端提交超过 10,000 个字符的 `message`
- **THEN** HTTP 接口返回 `422`
- **AND** 系统不调用 LLM Application

### Requirement: 系统校验并规范化对话输入

系统必须（MUST）拒绝空消息，并在 Application 层去除消息首尾空白后再调用 LLM Port。

#### Scenario: 空消息被 HTTP 契约拒绝

- **WHEN** 客户端提交空字符串作为 `message`
- **THEN** HTTP 接口返回 `422`

#### Scenario: 仅包含空白字符的消息被应用层拒绝

- **WHEN** 客户端提交只包含空白字符的 `message`
- **THEN** HTTP 接口返回 `400`
- **AND** 系统不调用 LLM Port

### Requirement: 系统映射 LLM 服务可用性和响应失败

系统必须（MUST）将配置缺失、上游调用失败和空模型响应转换为稳定的 HTTP 错误状态。

#### Scenario: LLM 服务未完成配置

- **WHEN** Chat Application 抛出 `ServiceNotConfiguredError`
- **THEN** HTTP 接口返回 `503`
- **AND** 响应包含可理解的错误原因

#### Scenario: 上游模型调用失败

- **WHEN** Chat Application 抛出 `UpstreamServiceError`
- **THEN** HTTP 接口返回 `502`
- **AND** 响应包含可理解的错误原因

#### Scenario: 模型返回空响应

- **WHEN** LLM Port 返回空内容
- **THEN** Chat Application 将其视为失败
- **AND** HTTP 接口返回 `502`

### Requirement: 前端展示单轮对话的完整请求生命周期

前端必须（MUST）通过统一 Axios Client 调用 LLM API，并向用户展示单轮请求的加载、成功、失败和重试状态。

#### Scenario: 用户发送有效消息

- **WHEN** 用户输入非空消息并发送
- **THEN** 页面展示用户消息和模型回答
- **AND** 展示模型标识、请求耗时和可用的 Token 信息

#### Scenario: 请求正在处理中

- **WHEN** LLM 请求尚未完成
- **THEN** 页面展示正在请求模型的状态
- **AND** 禁止重复发送同一时刻的请求

#### Scenario: 请求失败后用户重试

- **WHEN** LLM 请求失败
- **THEN** 页面展示错误信息和重试入口
- **AND** 重试使用原始失败请求内容

#### Scenario: 当前对话不宣称未实现的能力

- **WHEN** 用户查看当前 Chat 页面
- **THEN** 页面明确当前为单轮模型调用验证
- **AND** 不宣称支持会话历史、上下文记忆、流式输出、工具调用或 RAG 问答
