## Purpose

定义 GLM 显式 thinking 策略和普通 Chat 流式首个上游活动的受控处理，避免 reasoning 阶段被误判为首段超时，同时确保内部推理内容不会泄漏到浏览器或会话记录。

## Requirements

### Requirement: GLM 调用显式使用 Profile thinking 策略

系统 MUST 为每次 GLM Chat Completion 依据当前已选择的服务端 Profile 显式发送其 thinking 策略。该策略 MUST 同时用于普通 Chat、流式 Chat、结构化调用和 RAG 调用，且不得由 HTTP 请求、前端状态、Conversation 数据或模型输出决定。

#### Scenario: 资源包 Profile 用于普通 Chat

- **WHEN** 服务端选择 GLM `resource` Profile 并执行 Chat Completion
- **THEN** 请求显式携带该 Profile 配置的 thinking 策略
- **AND** 未配置覆盖时使用资源包默认的 `disabled`

#### Scenario: Coding Plan Profile 用于结构化调用

- **WHEN** 服务端选择 GLM `coding_plan` Profile 并执行结构化调用
- **THEN** 请求显式携带该 Profile 配置的 thinking 策略
- **AND** 未配置覆盖时使用 Coding Plan 默认的 `low`

### Requirement: 流式首段等待识别上游活动

系统 MUST 将 Provider 产生的可展示正文或 reasoning 视为流式上游活动。普通 Interaction Chat MUST 在首个上游活动到达时解除首段等待；reasoning 只可作为内部活动信号，不得作为 SSE `delta`、Conversation Message 或日志文本输出。

#### Scenario: reasoning 先于可展示正文

- **WHEN** GLM 流先返回 reasoning 且尚无可展示正文
- **THEN** 系统将该 chunk 视为已活动并返回既有的 `meta` SSE 事件
- **AND** 不发送空 `delta` 或 reasoning 内容
- **AND** 后续正文仍按既有 `delta.content` 字段返回

#### Scenario: 首段期间没有上游活动

- **WHEN** 流在 `LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS` 内既未产生正文也未产生 reasoning 活动
- **THEN** 系统关闭上游流并返回既有 `UPSTREAM_TIMEOUT` 错误事件
- **AND** 不返回 `complete` 事件
