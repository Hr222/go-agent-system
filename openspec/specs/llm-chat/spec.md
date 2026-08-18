# llm-chat 能力规格

## Purpose

定义独立 LLM 单轮对话的同步 HTTP、SSE 流式、Application 和前端可观察行为。

当前能力不包含会话历史、上下文记忆、工具调用、知识库引用或 Agent 编排。

## Requirements

### Requirement: 系统提供独立的单轮 LLM 对话契约

系统必须（MUST）通过 `POST /api/v1/llm/chat` 接收一条用户消息并返回完整的 JSON 响应；同时必须（MUST）通过 `POST /api/v1/llm/chat/stream` 提供流式响应。两个接口都只处理单轮请求，不包含会话历史、上下文记忆、工具调用或知识库引用。

#### Scenario: 有效消息返回单轮 JSON 响应

- **WHEN** 客户端向 `POST /api/v1/llm/chat` 提交长度在允许范围内且包含非空内容的 `message`
- **THEN** 系统调用一次 Chat Application
- **AND** 返回 `answer`、`model`、`prompt_version` 和 `usage` 字段
- **AND** 响应格式与流式能力加入前保持兼容

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

#### Scenario: 同步请求发生上游调用失败

- **WHEN** 同步 Chat Application 抛出 `UpstreamServiceError`
- **THEN** 同步接口返回 `502`
- **AND** 响应包含可理解的错误原因

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

系统 MUST 保留既有直接 LLM Chat API 的调用能力；平台 Chat 页面 MUST 通过服务端控制的交互流请求普通单轮对话，并向用户展示连接中、输出中、成功、取消、失败和显式重试状态。直接 `/api/v1/llm/chat` 与 `/api/v1/llm/chat/stream` 继续使用原有 HTTP 契约，普通 JSON 请求继续使用统一 Axios Client；带 POST JSON Body 的 SSE 流式请求必须通过 `services/http` 中的专用流式 HTTP 客户端读取，且不得由页面组件直接创建网络请求。

前端必须（MUST）按服务端接收顺序将每个有效 `delta` 追加到对应的助手消息。多个完整 SSE 帧即使在同一次底层读取中到达，也必须经过可观察的渲染调度。前端必须将已接收文本以用户可感知的受控节奏逐步展示；当单个 `delta` 包含多个可读字符组时，不得只在一个渲染中显示全部文本。展示节奏不得改变、遗漏、重复或重排任何文本；最终助手消息必须与按顺序拼接所有 `delta` 的结果一致。

前端必须（MUST）在待展示内容大量积压或流已终止时加速排空本地队列，避免展示动画无限延长回答完成时间。

#### Scenario: 用户发送有效普通对话并接收流式回答

- **WHEN** 用户在 Chat 页面输入非空普通对话消息并发起交互流请求
- **THEN** 页面立即展示用户消息和处于连接中的空助手消息
- **AND** 收到首个 `delta` 后将助手消息标记为正在输出
- **AND** 页面以可感知的节奏按接收顺序显示已接收文本，直到流式回答终止且待展示内容排空

#### Scenario: 多个增量在同一读取批次到达

- **WHEN** 流式 HTTP 客户端在一次 `ReadableStream` 读取中解析出多个 `delta` 事件
- **THEN** 页面按事件顺序将这些增量加入渲染队列
- **AND** 渲染调度器在动画帧中提交增量，而不是以同一批 React 状态更新直接覆盖为最终文本
- **AND** 助手消息的最终文本与按顺序拼接所有 `delta` 的结果一致

#### Scenario: 单个增量包含多段可读文本

- **WHEN** 前端收到包含多个可读字符组的单个 `delta`
- **THEN** 页面将其按原始顺序加入展示队列
- **AND** 页面在多个受控绘制时机逐步显示这些字符组
- **AND** 页面不拆坏 Unicode 字符、不改变空白和标点顺序

#### Scenario: 增量快速集中到达

- **WHEN** 多个 `delta` 在短时间内到达并形成待展示积压
- **THEN** 页面保持所有文本的接收顺序
- **AND** 页面提高每次展示的提交量以有限时间排空积压
- **AND** 页面不将积压文本无限期留在正在输出状态

#### Scenario: 流式回答正常完成

- **WHEN** 页面收到 `complete` 事件
- **THEN** 页面先展示所有已接收但尚未显示的文本
- **AND** 助手消息随后标记为已完成
- **AND** 页面展示模型标识、请求耗时和可用的 Token 信息

#### Scenario: 用户取消流式请求

- **WHEN** 用户在连接中或输出中取消流式请求
- **THEN** 页面停止读取新的流式内容
- **AND** 页面保留并排空取消前已接收的助手文本
- **AND** 助手消息标记为已取消而不是普通服务错误
- **AND** 页面允许用户再次发送新请求

#### Scenario: 流式回答产生部分内容后失败

- **WHEN** 已接收至少一个 `delta` 后流式请求失败或收到 SSE `error` 事件
- **THEN** 页面保留并排空失败前已接收的助手文本
- **AND** 助手消息标记为生成失败并显示可理解的错误信息
- **AND** 页面提供使用原始用户消息的显式重试入口
- **AND** 页面不自动重试

#### Scenario: 用户显式重试失败请求

- **WHEN** 用户点击失败消息的重试入口
- **THEN** 页面使用原始用户消息重新发起一次 Chat 请求
- **AND** 页面为本次新请求创建独立的助手消息状态
- **AND** 一次重试不会自动触发额外的重复请求

#### Scenario: 当前请求正在处理中

- **WHEN** LLM 请求处于连接中、输出中或正在排空已接收文本
- **THEN** 页面展示当前请求的准确状态
- **AND** 页面禁止重复发送同一时刻的请求
- **AND** 页面提供取消当前请求的操作

#### Scenario: 当前对话保持单轮能力边界

- **WHEN** 用户查看当前 Chat 页面
- **THEN** 页面明确当前为单轮模型调用验证
- **AND** 不宣称支持会话历史、上下文记忆、工具调用或 RAG 问答

#### Scenario: 直接 Chat 接口保持兼容

- **WHEN** 既有客户端请求 `/api/v1/llm/chat` 或 `/api/v1/llm/chat/stream`
- **THEN** 系统按既有单轮 Chat JSON 或 SSE 契约处理该请求
- **AND** 系统不要求既有客户端先经过交互路由
