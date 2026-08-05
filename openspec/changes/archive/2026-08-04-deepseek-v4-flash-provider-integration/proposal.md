## Why

当前 LLM 接入、诊断脚本和真实结构化 smoke 主要绑定智谱 GLM，无法通过已有的 LLM Port 和 Composition Root 选择另一套 OpenAI-compatible Provider。DeepSeek V4-Flash 已提供兼容的 Chat Completions 和 JSON Output，适合先作为可选 Provider 接入，同时保留现有 GLM 行为。

## What Changes

- 新增 DeepSeek V4-Flash 的 Provider 配置、OpenAI-compatible Client 组装和 Chat/Structured Adapter。
- 通过 Composition Root 选择 GLM 或 DeepSeek，保留现有 `ChatLlmPort`、`StreamingChatLlmPort`、`StructuredLlmPort`、结果模型和 GLM 配置。
- 为 DeepSeek Structured 调用配置 JSON Object 请求和 V4-Flash 的非 thinking 模式，确保请求适配 DeepSeek API。
- 将现有 LLM 诊断和单块结构化 smoke 改为 Provider-neutral 入口，脚本只负责参数解析、调用和脱敏输出。
- 增加 Fake Provider、Factory、Adapter、Composition Root 和真实 smoke 所需的回归验证。
- 本 Change 不新增 DeepSeek 专用业务字段转换，不修改 Tender 分块、全局归并、DOCX 渲染或 HTTP/MCP 契约；特殊返回格式归一化作为后续迭代处理。

## Capabilities

### New Capabilities

- `deepseek-v4-flash-provider`: 在不改变现有 LLM 应用契约的前提下，提供可选的 DeepSeek V4-Flash OpenAI-compatible Provider 接入和基础结构化调用验证。

### Modified Capabilities

无。现有 `llm-chat` 的同步 HTTP、SSE 和应用层行为保持不变。

## Impact

- 影响 `app/shared/config.py`、`app/infrastructure/llm/` 和 `app/composition/` 的 Provider 配置、Factory、Adapter 及组装逻辑。
- 影响 `tools/llm_provider_diagnostics.py`、`tools/tender_chunk_smoke.py` 的 Provider 选择方式，但保留原有 GLM 调用能力。
- 增加 DeepSeek API 凭据和模型配置；API Key 只从运行时环境读取，不写入日志、测试夹具或 Change 文档。
- 不修改数据库、持久化模型、HTTP 输入输出、MCP 协议、Tender Domain 或 DOCX 文件契约。
- 真实验证依赖可用的 DeepSeek API Key、`https://api.deepseek.com` 或明确配置的兼容 endpoint，以及可用的 `deepseek-v4-flash` 模型 ID。
