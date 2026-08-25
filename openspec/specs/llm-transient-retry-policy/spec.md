## Purpose

定义 OpenAI-compatible LLM 的唯一应用级瞬态失败重试策略，在控制 Provider 调用节奏的同时，保证流式 Conversation 不重复输出或持久化。

## Requirements

### Requirement: LLM 瞬态失败使用唯一的应用级重试策略

系统 MUST 在 OpenAI-compatible LLM 调用中使用唯一的应用级重试策略，SDK Client MUST 继续保持 `max_retries=0`。该策略 MUST 只将连接错误、超时、408、429 和 5xx 分类为可重试失败；鉴权、参数、内容安全、上下文限制及其他 4xx MUST 立即失败且不得重试。

#### Scenario: 同步调用遇到可恢复的上游错误

- **WHEN** Chat、结构化调用或 RAG 调用在最大尝试次数内遇到连接错误、超时、408、429 或 5xx，随后成功
- **THEN** 系统在应用层重试并返回该次成功结果
- **AND** SDK 不执行额外重试
- **AND** GLM 与 DeepSeek 使用相同的分类规则

#### Scenario: 同步调用遇到不可恢复的客户端错误

- **WHEN** 上游返回 400、401、403、404、409、422 或其他不属于 408/429 的 4xx
- **THEN** 系统保留既有受控上游失败语义
- **AND** 不发起后续请求尝试

### Requirement: 重试延迟受 Provider 指示和调用预算约束

系统 MUST 使用服务端配置的最大尝试次数、基础退避、最大退避、最大 `Retry-After` 和总退避预算来决定是否重试。429 响应包含可解析的 `Retry-After` 时，系统 MUST 优先使用该值；所有延迟 MUST 受配置上限保护。没有 `Retry-After` 的可重试失败 MUST 使用带抖动的指数退避。若下一次退避超出剩余预算，系统 MUST 停止重试且不得发送新的 Provider 请求。

#### Scenario: 限流响应要求等待

- **WHEN** Provider 返回 429 且 `Retry-After` 在受支持范围内，并且调用预算足够
- **THEN** 系统在该等待时间后再发起下一次尝试
- **AND** 不使用更短的指数退避覆盖 Provider 的限流指示

#### Scenario: 预算不足以等待下一次尝试

- **WHEN** 可重试失败后的等待时长超过剩余重试预算
- **THEN** 系统返回既有受控上游失败
- **AND** 不发起下一次 Provider 请求

### Requirement: 流式调用只在首个上游 activity 前重试

系统 MUST 仅在流式调用尚未向 Conversation Runtime 交付正文或 reasoning activity 时重试。每次失败的首 activity 前流 MUST 被关闭后再创建下一次尝试。首个 activity 已交付后，后续异常 MUST 保持既有错误映射且不得重试，避免重复 SSE 内容、重复 Assistant 消息或重复的 Provider 消耗。

#### Scenario: 首个 activity 前的瞬态失败恢复

- **WHEN** 流式 Chat 在首个正文或 reasoning activity 前遇到可重试失败，且后续尝试成功
- **THEN** 浏览器只收到一次既有的 `meta`、`delta` 和 `complete` 事件序列
- **AND** Conversation 只保存一个用户消息和一个 Assistant 消息

#### Scenario: 首个 activity 后发生流式错误

- **WHEN** 流式 Chat 已向 Conversation Runtime 交付首个 activity，随后发生错误
- **THEN** 系统不再创建新的 Provider 流
- **AND** Interaction 按既有安全 SSE 错误语义结束该请求

### Requirement: 重试过程不记录敏感调用内容

系统 MUST 为每次失败分类和实际重试记录 Provider、尝试序号、失败类别、状态码（如有）和等待时长。日志 MUST NOT 包含 API 密钥、Prompt、Conversation 消息正文、Schema 或模型输出。

#### Scenario: 记录重试决定

- **WHEN** 系统决定重试或因预算、次数、错误分类而停止重试
- **THEN** 日志提供足以定位重试决定的非敏感元数据
- **AND** 日志不包含调用的输入或输出文本
