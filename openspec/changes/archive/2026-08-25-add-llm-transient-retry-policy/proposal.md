## Why

同步与异步 SDK 已统一关闭隐式重试，但短暂网络故障、429 和 Provider 5xx 会立即暴露给用户。若由浏览器或 SDK 随意重试，既会重复消耗配额，也无法保证流式 Conversation 不重复写入。

## What Changes

- 为 OpenAI-compatible LLM 调用增加唯一的应用级瞬态失败重试策略，统一分类可重试和不可重试的上游失败。
- 对同步调用完整重试；对流式调用仅在任何上游 activity 送达前重试，首个 activity 后发生的错误保持既有受控错误路径。
- 支持受上限保护的 `Retry-After`、指数退避和抖动，并在退避会超过本次重试预算时止损。
- 记录不含密钥、Prompt 或模型输出的调用尝试与重试原因，便于定位 Provider 瞬态故障。

## Capabilities

### New Capabilities

- `llm-transient-retry-policy`: 定义 OpenAI-compatible LLM 的失败分类、预算化重试、流式首 activity 边界和安全日志行为。

### Modified Capabilities

无。

## Impact

- 影响 `app/infrastructure/llm` 中的 OpenAI-compatible Chat 与结构化 Adapter、LLM 配置和其自动化测试；GLM、DeepSeek 共用同一策略。
- 不改变 HTTP/SSE 契约、Conversation 持久化、数据库、模型选择、thinking 策略或前端代码。已有 SSE `error` 仍由 Interaction 层映射。
- 影响外部 Provider 的调用节奏：仅连接故障、超时、429、408 和 5xx 可进入受限重试；鉴权、参数、内容安全、上下文等其他 4xx 不重试。
- 不包含令牌桶限流、自适应并发、熔断、自动 Provider 降级、用户手动重试、非流式改流式或新的持久化状态。
