## ADDED Requirements

### Requirement: OpenAI-compatible 同步与异步 Client 使用一致配置

系统 MUST 通过同一个 Provider 配置组装 OpenAI-compatible 的同步与异步 Client。两个 Client MUST 使用相同的端点、认证信息、超时和显式 `max_retries=0`，且不得由 LangChain 或 SDK 隐式覆盖为默认重试次数。

#### Scenario: 创建 GLM 流式 Chat 模型

- **WHEN** Composition Root 为 GLM 创建流式 Chat 模型
- **THEN** 模型获得 Factory 创建的同步与异步 Completion Client
- **AND** 两个 Client 使用同一 GLM Profile 的端点、模型配置和零 SDK 重试策略

#### Scenario: 创建 DeepSeek 流式 Chat 模型

- **WHEN** Composition Root 为 DeepSeek 创建流式 Chat 模型
- **THEN** 模型获得 Factory 创建的同步与异步 Completion Client
- **AND** 两个 Client 使用同一 DeepSeek Provider 配置和零 SDK 重试策略

### Requirement: 异步 Client 在 Container 生命周期结束时关闭

系统 MUST 在全局或请求级 Application Container 结束时关闭 Factory 已创建的异步 Client。请求级流式响应 MUST 在其 Generator 完成或关闭后再触发资源清理；关闭不得改变既有 HTTP 或 SSE 内容。

#### Scenario: 流式请求正常结束

- **WHEN** 请求级 Container 承载的流式 Chat 正常结束
- **THEN** 系统在 SSE 结束后关闭该 Container 创建的异步 Client
- **AND** 浏览器继续收到既有的 `meta`、`delta`、`complete` 或受控 `error` 事件

#### Scenario: 流式请求被取消

- **WHEN** 浏览器断开或流式 Generator 被关闭
- **THEN** 系统先执行既有上游流关闭语义
- **AND** 随后关闭请求级 Container 创建的异步 Client
- **AND** 不因资源清理额外发送 SSE 事件
