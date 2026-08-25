## Context

`OpenAICompatibleClientFactory` 已同时为同步和异步 SDK Client 显式设置 `max_retries=0`，因此 Provider 调用当前立即暴露连接错误、超时、429 和 5xx。现有 Chat、结构化和 RAG Adapter 分别在基础设施层发起这些调用；流式 Conversation 在开始生成前已写入用户消息，首个 activity 之后才会将 Assistant 消息在成功完成后写入。

重试不能放在 HTTP 层或 Conversation Runtime：前者不了解 Provider 错误类别，后者会重新执行已持久化的回合准备，造成重复用户消息。它属于 `infrastructure/llm` 的外部 SDK 调用治理；Application、Domain、HTTP Schema 和前端不感知重试细节。

## Goals / Non-Goals

**Goals:**

- 为所有 OpenAI-compatible 的同步调用和流式 Chat 提供一个可替换、可测试的应用级瞬态失败重试策略。
- 使用 408、429、5xx、连接错误和超时的明确分类，按 `Retry-After` 或带抖动的指数退避决定下一次尝试。
- 让同步调用只返回最终成功或既有受控上游错误；让流式调用仅在首个 activity 前隐藏重试。
- 将最大尝试数、退避和预算放入服务端配置，日志仅保留安全的诊断元数据。

**Non-Goals:**

- 不实现令牌桶、请求队列、自适应并发、熔断、自动 Provider 降级或用户手动重试。
- 不将结构化或 RAG 同步调用改为伪流式，也不修改模型、thinking、输出上限或 HTTP/SSE 字段。
- 不重试首个 activity 已经发送后的流式错误，不新增 Conversation 状态或数据库迁移。

## Decisions

### 将重试组件放在 Infrastructure Adapter 内部

新增 Provider-neutral 的 `LlmTransientRetryPolicy`，由 OpenAI-compatible Chat、结构化和 RAG Adapter 共享。Factory 只负责 SDK Client 构造与关闭，保持 `max_retries=0`；Adapter 在调用 `invoke()`、`chat.completions.create()` 或 `astream()` 时使用策略。

这保留了现有依赖方向：业务 Port 不增加 SDK 异常或重试参数，Composition Root 继续只注入 Factory。替代方案是在 HTTP Route 重试，因其无法区分所有 Adapter 调用且会重放 Conversation 准备，故不采用。

### 明确失败分类和延迟计算

策略将 OpenAI SDK 的连接和超时异常、Python/HTTPX 的传输与超时异常，以及 408、429、500 至 599 视为可重试；其他异常保守地停止。429 优先解析 `Retry-After` 秒数，超过 `LLM_RETRY_MAX_RETRY_AFTER_SECONDS` 时截断；没有有效值时使用 `base * 2^n` 并加入不超过当前退避 25% 的随机抖动，同时受最大退避限制。

默认配置为两次总尝试、1 秒基础退避、8 秒最大退避、30 秒最大 `Retry-After` 与 30 秒总退避预算。下一次等待会使累计等待超过预算时，策略保留最后一个原始异常且不再调用 Provider。默认值降低短暂抖动对用户的影响，并避免 SDK、服务端和浏览器三层叠加重试。

替代方案是让 SDK 重试后只在外层记录日志；这会再次出现同步/异步路径不一致且无法遵守 Provider 的 `Retry-After`，故不采用。

### 流式重试以首个 activity 为提交边界

流式 Adapter 在每次尝试中等待首个正文或 reasoning activity，期间出现可重试异常或首 activity 超时才关闭该上游流、等待并重试。一旦向 Streaming Conversation Runtime yield 任何 activity，策略即进入不可重试状态；后续错误由既有 Adapter 和 Interaction 路径映射。

为使内层策略有机会完成重试，Interaction 的首 activity 等待窗口改为 `单次首 activity 超时 × 最大尝试数 + 最大总退避预算`。每个 Adapter 尝试仍受原 `LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS` 限制，避免无响应 Provider 占用无限时间。Assistant 消息仍只在完整流成功后写入。

替代方案是在 Conversation Runtime 重试整个 `execute()`；它会重复写入本回合用户消息，故不采用。首个 activity 后继续重试会重放浏览器内容或创建不确定的上游结果，故明确禁止。

### 安全日志和可注入测试依赖

策略日志只记录 Provider、尝试数、可重试类别、HTTP 状态、计算出的等待时间和停止原因。睡眠、时钟与随机数通过构造函数可注入，使 429、抖动、预算止损和流关闭测试无需联网或真实等待。

不记录异常文本，因为其可能携带上游回显的 Prompt 或敏感内容；现有 HTTP 边界继续负责将错误映射为浏览器安全消息。

## Risks / Trade-offs

- [瞬态失败使首个 SSE 事件等待更久] → 最大两次尝试和 30 秒总退避预算受服务端配置约束；前端无需理解新增内部尝试。
- [错误类型的 SDK 包装在升级后改变] → 同时覆盖公开 OpenAI/HTTPX 异常与状态码，未知类型保守失败，并用替身测试锁定现有依赖行为。
- [429 的 Retry-After 过大] → 读取值和累计等待均设上限，超过剩余预算立即止损。
- [流关闭失败] → 以 `finally` 关闭每个失败流，关闭异常不覆盖主失败；现有请求级 Container 继续释放异步 SDK Client。
- [同步调用的单次网络等待仍可能较长] → 本 Change 不改变 Provider timeout；后续独立 Change 再评估按调用路径调整模型、输出预算与伪流式聚合。

## Migration Plan

1. 发布无需数据库迁移、HTTP 或前端配置变更；默认策略立即生效，也可由服务端环境变量收紧或关闭额外尝试。
2. 部署后观察不含内容的尝试、状态码与退避日志，确认 429 和 5xx 不发生重试风暴。
3. 发现 Provider 或成本风险时，将最大尝试次数设为 1 即可停用应用级重试；回滚代码不会影响已保存的 Conversation。

## Open Questions

无阻塞问题。令牌桶限流与熔断需要依据实际套餐限额和观测数据在后续独立 Change 中确定。
