## Why

当前 GLM 已经能够返回结构化的招标分析内容，但不同模型可能使用额外的结果包装、思考字段、Markdown 代码块或其他非标准表达，导致现有适配器在 Schema 校验前直接失败。需要在 Provider 原始响应和业务结构化结果之间增加稳定的归一化边界，让 Tender Agent 保持现有业务契约，同时为未来接入不同输出格式的 LLM 预留扩展入口。

## What Changes

- 新增结构化 LLM 输出归一化能力，统一处理 Provider 原始响应提取、已知包装解包、思考内容隔离、JSON 内容提取和最终 Schema 校验。
- 将 Provider 调用与结构化结果归一化分离，保留现有 `StructuredLlmPort` 和 `StructuredLlmResult` 契约不变。
- 实现 OpenAI-compatible Provider 返回格式的通用归一化，包括 `tender_analysis`、`tender_chunk_analysis` 等按目标 Schema 推导的包装对象。
- GLM 和 DeepSeek 共用确定性的 Schema 感知 JSON 归一化器；同时保留按 Provider 或模型扩展真正特殊输出格式的接口，不修改 Tender Application、分块归并或 MCP 业务代码。
- 对无法安全归一化、字段结构不符合目标 Schema 或格式存在歧义的响应返回稳定的结构化调用失败，不静默丢弃思考内容或编造字段。
- 增加直接 JSON、包装 JSON、代码块、思考字段和不兼容格式的 Fake/Adapter 测试，并用真实 GLM 验证归一化后能够继续进入 Tender Application 的 Schema 校验和骨架渲染链路。

## Capabilities

### New Capabilities

- `structured-llm-output-normalization`: 定义 Provider 原始结构化响应的提取、归一化、扩展和失败隔离行为。

### Modified Capabilities

无。现有 Tender HTTP、MCP、`StructuredLlmPort` 和 Tender Application 的外部行为契约保持不变；本 Change 只增加其下方的基础设施归一化能力。

## Impact

- 影响 `app/infrastructure/llm/` 中的结构化 Provider 适配器、原始响应解析和 Composition Root 组装。
- 可能新增 Provider 输出归一化接口、通用 Schema 感知 JSON 归一化实现、归一化装饰器及其测试替身。
- 不修改数据库、HTTP/MCP 输入输出、Tender Domain/Application、前端页面或 DOCX 渲染职责。
- 覆盖现有 GLM 和 DeepSeek 结构化适配器；不在本 Change 中实现无确定规则的 Provider 专属自然语言格式。
- 日志只记录 Provider、模型、响应格式分类、Schema、耗时和失败类型，不记录思考原文、招标正文、API Key 或完整模型响应。
