## ADDED Requirements

### Requirement: 系统可以选择 DeepSeek V4-Flash Provider

系统 MUST 通过 Composition Root 根据运行时 Provider 配置组装 DeepSeek V4-Flash LLM 能力，并继续支持现有 GLM 组装路径。Provider 选择不得进入 Tender Application、Chat Application 或 Domain 代码。

#### Scenario: 使用 DeepSeek 配置组装 LLM

- **WHEN** 运行时配置选择 DeepSeek，并提供 API Key、Base URL 和模型标识
- **THEN** Composition Root 返回实现现有 LLM Port 的 DeepSeek Adapter
- **AND** Adapter 使用配置的 Base URL 和模型标识创建 OpenAI-compatible Client
- **AND** 应用层不需要修改现有 LLM 调用方式

#### Scenario: 未选择 DeepSeek 时保持 GLM

- **WHEN** 运行时配置保持现有 GLM Provider
- **THEN** Composition Root 继续组装现有 GLM Adapter
- **AND** GLM 的配置、Port、Result 和现有测试行为保持兼容

### Requirement: DeepSeek Structured 调用返回现有结构化结果

DeepSeek Structured Adapter MUST 使用现有 `StructuredLlmPort` 和 `StructuredLlmResult` 契约。对于直接符合目标 Pydantic Schema 的 JSON object，系统 MUST 在不增加业务字段转换的情况下完成本地 Schema 校验并返回结构化结果。

#### Scenario: DeepSeek 返回直接 JSON object

- **WHEN** DeepSeek 返回目标 Schema 顶层字段组成的合法 JSON object
- **THEN** Adapter 将 Provider 响应交给现有结构化装饰层
- **AND** 装饰层完成目标 Schema 校验
- **AND** 调用方收到包含 `value`、模型标识和 Prompt 版本的 `StructuredLlmResult`

#### Scenario: DeepSeek 请求使用 JSON Object 和非 thinking 模式

- **WHEN** Adapter 发起 Structured 请求
- **THEN** 请求包含 `response_format={"type":"json_object"}`
- **AND** 请求明确关闭 DeepSeek thinking 模式
- **AND** Prompt 包含明确的 JSON 输出要求和目标 Schema

#### Scenario: DeepSeek 返回 reasoning_content

- **WHEN** Provider 响应同时包含 `content` 和 `reasoning_content`
- **THEN** 系统只使用业务 `content` 进行结构化校验
- **AND** `reasoning_content` 不进入 `StructuredLlmResult.value`
- **AND** 系统不把 reasoning 文本返回到 HTTP、MCP 或业务日志

### Requirement: 不兼容的 DeepSeek 结构保持失败闭合

DeepSeek Adapter MUST 对空响应、无效 JSON、字段类型错误和无法直接校验的返回保持现有结构化失败语义。系统 MUST NOT 在本 Change 中猜测字段、静默丢字段或再次调用 LLM 修复结果。

#### Scenario: DeepSeek 返回无法校验的 JSON

- **WHEN** Provider 返回空内容、无效 JSON 或不符合目标 Schema 的 JSON object
- **THEN** Structured 调用返回现有上游或结构化失败
- **AND** 调用方不收到未经 Schema 校验的业务结果
- **AND** 诊断日志只包含 Provider、模型、Schema、阶段、响应格式、耗时和异常类型

### Requirement: LLM MVP 脚本支持 Provider-neutral 验证

诊断和单块 Structured smoke 脚本 MUST 通过 Provider 配置或 Composition Root 选择 LLM，不得直接依赖 GLM 专属环境变量或具体 Adapter。脚本输出 MUST 脱敏，不得输出 API Key、完整 Prompt、完整响应或招标正文。

#### Scenario: 运行 DeepSeek 普通 Chat 和 JSON smoke

- **WHEN** 使用 DeepSeek 配置运行 MVP 脚本
- **THEN** 脚本可以分别验证网络可达性、普通 Chat 和 JSON Object 响应
- **AND** 输出包含模型、状态、耗时、响应格式和响应长度等诊断字段
- **AND** 输出不包含 API Key 或完整 Provider 响应

#### Scenario: 运行单块 Tender Structured smoke

- **WHEN** 使用 DeepSeek 配置运行单块 Tender smoke
- **THEN** 脚本构造现有 `TenderChunk` 请求并调用现有 Structured Port
- **AND** 返回结果必须通过 `TenderChunkAnalysis` 本地校验
- **AND** 该 smoke 不宣称完成 Tender 全局归并或 DOCX 业务验收
