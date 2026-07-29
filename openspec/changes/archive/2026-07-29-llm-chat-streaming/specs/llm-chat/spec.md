# llm-chat 能力增量规格

## MODIFIED Requirements

### Requirement: 系统提供独立的单轮 LLM 对话契约

系统必须（MUST）通过 `POST /api/v1/llm/chat` 接收一条用户消息并返回完整的 JSON 响应；同时必须（MUST）通过 `POST /api/v1/llm/chat/stream` 提供流式响应。两个接口都只处理单轮请求，不包含会话历史、上下文记忆、工具调用或知识库引用。

#### Scenario: 有效消息返回单轮 JSON 响应

- **WHEN** 客户端向 `POST /api/v1/llm/chat` 提交长度在允许范围内且包含非空内容的 `message`
- **THEN** 系统调用一次 Chat Application
- **AND** 返回 `answer`、`model`、`prompt_version` 和 `usage` 字段
- **AND** 响应格式与本次变更前保持兼容

#### Scenario: 超过契约长度限制的消息被拒绝

- **WHEN** 客户端向任一 Chat 接口提交超过 10,000 个字符的 `message`
- **THEN** HTTP 接口返回 `422`
- **AND** 系统不调用 LLM Application

#### Scenario: 有效消息建立流式响应

- **WHEN** 客户端向 `POST /api/v1/llm/chat/stream` 提交合法的单轮消息
- **THEN** 系统返回 `text/event-stream` 响应
- **AND** 第一个非心跳事件为 `meta`
- **AND** `meta` 事件包含 `request_id`、`model` 和 `prompt_version`
- **AND** 系统按模型生成顺序发送一个或多个 `delta` 事件
- **AND** 每个 `delta` 事件包含本次新增的文本内容
- **AND** 正常完成时发送一个 `complete` 事件
- **AND** `complete` 事件包含 `request_id`、模型标识和可用的 Token 使用信息

#### Scenario: 流式响应保持单轮能力边界

- **WHEN** 客户端使用流式 Chat 接口完成一次请求
- **THEN** 流中只包含当前用户消息对应的模型回答
- **AND** 流中不包含会话历史、工具调用、知识库引用或 Agent 编排结果

### Requirement: 系统校验并规范化对话输入

系统必须（MUST）对同步和流式 Chat 接口使用一致的输入校验规则，拒绝空消息，并在调用 LLM 能力前去除消息首尾空白。

#### Scenario: 空消息被 HTTP 契约拒绝

- **WHEN** 客户端向任一 Chat 接口提交空字符串作为 `message`
- **THEN** HTTP 接口返回 `422`
- **AND** 系统不调用 LLM Application

#### Scenario: 仅包含空白字符的消息被应用层拒绝

- **WHEN** 客户端向任一 Chat 接口提交只包含空白字符的 `message`
- **THEN** HTTP 接口返回 `400`
- **AND** 系统不调用 LLM Port

#### Scenario: 合法消息在调用前被规范化

- **WHEN** 客户端提交首尾包含空白字符但中间包含有效内容的 `message`
- **THEN** 系统去除首尾空白后调用 LLM 能力
- **AND** 同步接口和流式接口使用相同的规范化消息

### Requirement: 系统映射 LLM 服务可用性和响应失败

系统必须（MUST）为同步和流式 Chat 请求提供稳定、可区分且不泄露敏感信息的失败表达。流式响应开始前使用 HTTP 状态表达错误；流式响应开始后使用 SSE `error` 事件表达错误。

#### Scenario: LLM 服务未完成配置

- **WHEN** Chat Application 判定 LLM 服务未完成配置
- **THEN** 同步接口返回 `503`
- **AND** 流式接口在响应开始前返回 `503`
- **AND** 响应不包含 API Key 或 Provider 异常原文

#### Scenario: 流式响应开始前上游调用失败

- **WHEN** Provider 在流式响应开始前调用失败
- **THEN** 流式接口返回 `502`
- **AND** 系统不发送 `delta` 或 `complete` 事件
- **AND** 响应不包含未经审查的 Provider 异常原文

#### Scenario: 流式响应开始前发生上游超时

- **WHEN** Provider 在流式响应开始前发生超时
- **THEN** 流式接口返回 `504`
- **AND** 响应包含稳定的错误原因
- **AND** 系统释放本次请求占用的资源

#### Scenario: 流式请求超过并发容量

- **WHEN** 系统无法为新的流式请求提供并发容量
- **THEN** 流式接口返回 `429`
- **AND** 系统不调用 Provider

#### Scenario: 流式响应开始后上游调用失败

- **WHEN** Provider 已经产生部分输出且后续调用失败
- **THEN** 系统发送一个 SSE `error` 事件
- **AND** `error` 事件包含稳定错误码、可展示的错误信息、`request_id` 和是否可重试的标识
- **AND** 系统关闭流式响应
- **AND** 系统不再发送 `complete` 事件

#### Scenario: 模型返回空响应

- **WHEN** LLM 能力未产生有效回答内容
- **THEN** 同步接口返回 `502`
- **AND** 流式接口在响应尚未开始时返回 `502`，或在响应已经开始后发送 SSE `error` 事件
- **AND** 系统不将空响应标记为成功完成

#### Scenario: 客户端取消流式请求

- **WHEN** 客户端主动关闭流式连接
- **THEN** 系统停止继续消费 Provider 流
- **AND** 系统释放本次请求占用的 Provider 资源和并发容量
- **AND** 系统不将客户端取消记录为普通 Provider 失败

### Requirement: 前端展示单轮对话的完整请求生命周期

前端必须（MUST）通过业务请求层调用对应的 Chat 接口，并向用户展示同步或流式单轮请求的连接中、生成中、成功、取消、失败和显式重试状态。

#### Scenario: 用户发送有效消息并接收流式回答

- **WHEN** 用户输入非空消息并发送流式 Chat 请求
- **THEN** 页面立即展示用户消息和生成中的助手消息
- **AND** 页面按接收顺序追加模型增量内容
- **AND** 流式请求正常完成后展示模型标识、请求耗时和可用的 Token 信息

#### Scenario: 流式请求正在处理中

- **WHEN** 流式 Chat 请求处于连接中或生成中状态
- **THEN** 页面展示当前请求状态
- **AND** 禁止重复发送同一时刻的请求
- **AND** 提供取消当前请求的操作

#### Scenario: 用户取消流式请求

- **WHEN** 用户在模型生成过程中取消请求
- **THEN** 页面停止继续读取流式内容
- **AND** 保留已经接收的助手文本
- **AND** 将助手消息标记为已取消
- **AND** 不将取消展示为普通服务错误

#### Scenario: 流式回答产生部分内容后失败

- **WHEN** 流式请求已经展示部分助手文本后收到错误
- **THEN** 页面保留已经接收的文本
- **AND** 页面展示可理解的失败状态和错误信息
- **AND** 页面提供显式重试入口
- **AND** 系统不自动重新发起请求

#### Scenario: 用户显式重试失败请求

- **WHEN** 用户点击失败消息的重试入口
- **THEN** 页面使用原始用户消息重新发起一次 Chat 请求
- **AND** 页面为本次新请求创建独立的助手消息状态
- **AND** 一次重试不会自动触发额外的重复请求

#### Scenario: 当前 Chat 页面保持单轮能力边界

- **WHEN** 用户查看当前 Chat 页面
- **THEN** 页面可以展示流式单轮模型调用状态
- **AND** 页面不宣称支持会话历史、上下文记忆、工具调用或 RAG 问答
