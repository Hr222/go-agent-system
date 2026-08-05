## Context

当前 LLM 应用层已经通过 `ChatLlmPort`、`StreamingChatLlmPort` 和 `StructuredLlmPort` 隔离 Provider。`StructuredLlmResult`、`RawStructuredLlmResponse` 和 `NormalizingStructuredLlm` 也已经提供了原始响应到业务结果之间的边界。

现有基础设施仍以 GLM 为默认实现：配置字段使用 `zhipu_*`，Factory 只读取智谱配置，结构化 Adapter 和诊断脚本直接使用 GLM。DeepSeek V4-Flash 兼容 OpenAI Chat Completions，并支持 JSON Object；官方文档要求 JSON 模式显式发送 `response_format`，V4 默认开启 thinking，因此结构化请求需要明确关闭 thinking。参考：[JSON Output](https://api-docs.deepseek.com/guides/json_mode) 和 [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)。

本 Change 只建立 DeepSeek Provider 接入和基础验证链路。真实 Tender Application 的分块规划、全局归并和 DOCX 渲染不在本次范围内；`tools/tender_chunk_smoke.py` 只作为单块 Provider smoke 使用。

## Goals / Non-Goals

**Goals:**

- 在不改变现有 LLM Port、Result 和应用层调用方式的情况下接入 DeepSeek V4-Flash。
- 让 GLM 和 DeepSeek 通过 Composition Root 可选，并保留 GLM 的现有配置和行为。
- 为 DeepSeek Structured 调用发送 OpenAI-compatible JSON Object 请求，并关闭 thinking 模式。
- 让现有诊断和单块结构化 smoke 通过 Provider 配置运行，而不是直接绑定 GLM 类名或环境变量。
- 验证 DeepSeek 的直接 JSON 结果可以进入现有 Pydantic Schema 和 `StructuredLlmResult` 链路。

**Non-Goals:**

- 不新增 DeepSeek 专用业务字段映射、包装解包或二次 LLM 修复逻辑。
- 不重写现有结构化输出归一化协议；特殊返回格式作为后续迭代处理。
- 不修改 Tender Application、分块算法、全局归并、DOCX Renderer、HTTP 或 MCP 契约。
- 不删除 GLM Adapter、GLM 配置或 GLM 测试。
- 不引入新的 LLM SDK；继续使用现有 OpenAI-compatible Client 和 LangChain 依赖。

## Decisions

### 1. 通过 Provider 配置扩展现有 Factory

Factory 保留现有 `create_client()` 和 `create_chat_model(model=...)` 能力，但内部改为接收已解析的 Provider 配置。配置至少包含 Provider 标识、API Key、Base URL、模型、超时、温度、最大输出和 DeepSeek thinking 选项。

GLM 的旧字段和调用路径继续可用；Composition Root 根据 Provider 选择组装对应实现。默认保持 GLM，切换到 DeepSeek 只需要运行时配置，不在 Tender Application 中增加 Provider 分支。

备选方案是新增一套完全独立的 DeepSeek Factory。该方案可以减少初始改动，但会复制 Client 缓存、超时和错误处理，后续 Provider 扩展成本更高，因此不采用。

### 2. 复用现有 LLM Port 和结果初始化边界

DeepSeek Adapter 必须实现现有 `ChatLlmPort`、`StreamingChatLlmPort` 或 `StructuredLlmPort`。成功结果继续由现有 `ChatLlmResult`、`StructuredLlmResult` 表示，Application 不接触 DeepSeek SDK 响应。

Structured Adapter 只负责发送请求、提取 OpenAI-compatible 响应并交给现有装饰层。对于直接符合目标 Schema 的 JSON，不增加 DeepSeek 专用转换；字段错误、空响应或不兼容结构继续按现有失败闭合路径处理。

### 3. DeepSeek Structured 请求固定为 JSON Object 和非 thinking

DeepSeek V4-Flash 的结构化请求发送 `response_format={"type":"json_object"}`，并通过 Provider 请求扩展参数关闭 thinking。Prompt 中保留明确的 JSON 输出要求和目标 Schema。普通 Chat 请求不强制使用 JSON Object，但仍使用相同的 Chat Port。

该选择优先保证 Tender 分块等结构化调用的响应内容可直接解析。DeepSeek `reasoning_content` 即使出现在响应中，也只能作为原始响应元数据，不进入业务结果。

### 4. tools 只保留为薄 CLI 驱动

诊断脚本负责读取参数、选择 Provider、执行普通 Chat 或单块 Structured smoke，并输出脱敏的状态、模型、耗时、响应格式和字符数。Client 创建、请求策略、响应提取和错误映射归属 `app/infrastructure/llm` 与 Composition Root。

`tender_v1_sample_probe.py` 继续作为确定性 Fake 结构探针，不伪装成真实 Provider 验收；真实 Tender HTTP/MCP 入口不由本 Change 改造。

## Risks / Trade-offs

- [Risk] DeepSeek API Key、模型 ID 或兼容 endpoint 配置错误。→ [Mitigation] 启动前检查必需配置，MVP 脚本先执行脱敏网络和模型可用性检查。
- [Risk] V4 默认 thinking 或输出截断导致结构化结果为空或不可解析。→ [Mitigation] Structured 请求明确关闭 thinking，设置合理的最大输出，并保留现有严格 Schema 校验和失败日志。
- [Risk] Provider-neutral Factory 改动影响现有 GLM。→ [Mitigation] 保留旧 GLM 配置兼容路径，增加 Factory/Composition Root 回归测试，默认仍使用 GLM。
- [Risk] 诊断脚本继续承载 Provider 细节。→ [Mitigation] 脚本只调用 Composition Root 或通用 LLM 入口，不直接构造 GLM/DeepSeek 具体 Adapter。
- [Risk] DeepSeek 返回特殊包装或字段结构需要额外转换。→ [Mitigation] 本 Change 不猜测、不丢字段、不二次调用 LLM；记录为后续归一化迭代。

## Migration Plan

1. 增加 DeepSeek 运行时配置，默认 Provider 保持 GLM。
2. 先运行 Provider-neutral MVP 诊断和 Fake 回归测试。
3. 配置 DeepSeek V4-Flash 后运行普通 Chat、JSON Object 和单块 Tender Structured smoke。
4. 发现 DeepSeek 特殊返回格式时，不在本 Change 中静默修复，记录为后续迭代。
5. 回滚时将 Provider 配置切回 GLM，不涉及数据库、持久化或 HTTP 契约迁移。

## Open Questions

- 真实环境使用的 DeepSeek API Key、Base URL 是否为官方 `https://api.deepseek.com`。
- 运行时是否使用官方模型名 `deepseek-v4-flash`，还是账号侧提供的兼容别名。
