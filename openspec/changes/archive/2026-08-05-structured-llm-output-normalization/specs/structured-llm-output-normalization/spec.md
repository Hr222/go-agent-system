## ADDED Requirements

### Requirement: 系统在业务结构化校验前归一化 Provider 原始响应

系统 MUST 在 Provider 原始结构化响应和业务 Pydantic Schema 校验之间执行归一化，并在归一化成功后继续返回现有 `StructuredLlmResult`。Tender Application、HTTP 和 MCP 不得感知 Provider 的包装格式、思考字段或原始文本格式。

#### Scenario: Provider 返回目标 Schema 的直接 JSON object

- **WHEN** Provider 返回字段直接位于目标 Schema 顶层的合法 JSON object
- **THEN** 归一化层保留该 object
- **AND** 系统使用目标 Schema 完成严格校验
- **AND** 调用方收到现有格式的 `StructuredLlmResult`

#### Scenario: Provider 返回已知 Schema 包装 JSON object

- **WHEN** Provider 返回 `tender_analysis` 或 `tender_chunk_analysis` 包装对象，且包装内容符合请求的目标 Schema
- **THEN** Schema 感知归一化器解包该已知包装
- **AND** 系统对解包后的内容执行严格 Schema 校验
- **AND** Tender Application 继续执行后续归并或骨架渲染

### Requirement: 系统通过可扩展接口隔离不同 Provider 的输出格式

系统 MUST 提供 Provider 输出归一化接口或等价的可替换扩展边界。具体 Provider 的归一化实现 MUST 只能通过该边界接入，不能要求 Tender Application、Tender Domain、HTTP 或 MCP 增加 Provider 分支。

#### Scenario: 增加新的 Provider 归一化器

- **WHEN** 新 Provider 的响应格式与 GLM 不同
- **THEN** 系统可以注册该 Provider 或模型对应的归一化器
- **AND** 该归一化器可以把其确定的原始格式转换为目标 Schema 输入
- **AND** 现有 Tender Application 和 `StructuredLlmPort` 不需要修改

#### Scenario: 多个 Provider 使用相同 JSON 表达

- **WHEN** GLM 和 DeepSeek 返回相同的直接 JSON 或目标 Schema 包装 JSON
- **THEN** Composition Root 为两个 Provider 选择同一个通用 Schema 感知归一化规则
- **AND** 系统不为相同 JSON 表达复制 Provider 专属归一化逻辑

#### Scenario: 未注册 Provider 格式

- **WHEN** Provider 返回系统没有对应归一化规则的格式
- **THEN** 系统返回稳定的结构化调用失败
- **AND** 系统不生成未经校验的 Tender 分析或骨架文件
- **AND** 错误中不包含思考原文、招标正文、API Key 或完整 Provider 响应

### Requirement: 系统隔离思考内容并处理明确的结构化表达

系统 MUST 优先从 Provider 的业务内容字段取得结构化结果，不得把独立思考字段混入业务 JSON。系统 MAY 处理明确标记的 Markdown JSON 代码块或思考标签，但不得把无法确认边界的普通文本静默当作业务结果。

#### Scenario: Provider 返回独立思考字段和业务 JSON

- **WHEN** Provider 在独立字段返回思考内容，并在业务内容字段返回合法 JSON object
- **THEN** 归一化层只使用业务内容字段进行 Schema 校验
- **AND** 思考内容不进入 `StructuredLlmResult`、HTTP/MCP 响应或日志正文

#### Scenario: Provider 返回 Markdown JSON 代码块

- **WHEN** Provider 的业务内容是包裹在明确 JSON 代码块中的合法 JSON object
- **THEN** 归一化层去除代码块标记并解析其中的 JSON object
- **AND** 系统继续执行目标 Schema 校验

### Requirement: 系统禁止不确定的业务字段猜测

系统 MUST 对归一化后的结果执行目标 Schema 严格校验。字段类型不匹配、多个包装对象无法区分、普通文本缺少确定解析规则或 JSON 内容不完整时，系统 MUST 返回稳定失败，不得通过丢字段、字符串化对象或再次调用 LLM 来伪造合法结果。

#### Scenario: Provider 返回字段类型不匹配

- **WHEN** Provider 返回的字段无法映射到目标 Schema 的声明类型
- **THEN** 系统返回结构化归一化失败
- **AND** 系统不进入 Tender Application 的成功分支
- **AND** 失败日志只记录 Provider、模型、Schema、格式分类和异常类型

#### Scenario: Provider 返回多个未知包装对象

- **WHEN** JSON object 同时包含多个无法依据目标 Schema 或 Provider 规则确定的候选结果
- **THEN** 系统返回结构化归一化失败
- **AND** 系统不静默选择其中一个结果

### Requirement: 归一化过程保持安全日志和现有错误边界

系统 MUST 继续使用现有结构化 LLM 和 Tender 错误映射，并在归一化阶段记录足以诊断格式问题的脱敏信息。系统不得记录招标正文、用户关注点、API Key、思考原文或完整模型响应。

#### Scenario: 归一化成功

- **WHEN** Provider 响应经过对应归一化器处理并通过目标 Schema 校验
- **THEN** 系统返回模型标识、Prompt 版本和已校验的结构化值
- **AND** 后续业务流程使用与 Provider 无关的统一契约

#### Scenario: 归一化失败

- **WHEN** Provider 响应无法安全转换或 Schema 校验失败
- **THEN** 系统返回现有稳定的上游或结构化分析失败
- **AND** 日志包含阶段、Provider、模型、Schema、响应格式分类、耗时和异常类型
- **AND** 日志和用户响应不包含敏感原文
