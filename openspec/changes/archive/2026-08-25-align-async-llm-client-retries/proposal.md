## Why

当前 Factory 只创建同步 OpenAI Client。LangChain 在流式 Chat 时会自行创建异步 Client，并恢复 OpenAI SDK 默认的两次重试，使流式路径的实际等待和重试次数与同步路径不一致。

## What Changes

- 让 OpenAI-compatible Client Factory 同时创建、缓存和关闭同步与异步 Client，并为两者使用相同的 Provider 配置、超时和零 SDK 重试策略。
- 将 Factory 管理的同步与异步 Completion Client 一并注入 `ChatOpenAI`，禁止 LangChain 在流式路径自行创建异步 SDK Client。
- 在 FastAPI 的请求级 Container 清理与全局 Container 关闭中等待异步 Client 关闭，避免流式完成后遗留连接池。
- 增加配置组装、流式模型注入和关闭行为测试；不引入应用级重试或改变错误映射。

## Capabilities

### New Capabilities

- `openai-compatible-async-client`: 定义 OpenAI-compatible Provider 的同步/异步 Client 一致配置、显式注入和受控关闭行为。

### Modified Capabilities

无。

## Impact

- 影响 LLM 基础设施 Factory、Composition Root 和 HTTP 依赖生命周期；GLM、DeepSeek 共用该行为。
- 不改变 HTTP/SSE 契约、数据库、Conversation 状态、模型选择、thinking 策略或浏览器代码。
- 外部 Provider 请求仍由现有 Adapter 发起，但 SDK 不再进行隐式重试；密钥、Prompt 与模型输出不会记录。
- 不包含 429/5xx 的应用级重试、Retry-After、退避、限流、熔断或降级，这些需要后续独立 Change。
