## Context

当前的 GLM resource 与 Coding Plan 已有独立端点、模型、thinking 和重试策略。`LLM_STREAM_MAX_CONCURRENCY` 是 HTTP 路由上的 `asyncio.Semaphore`，只会限制浏览器普通对话流；RAG、结构化意图、Agent 结构化输出以及每次重试均可绕过它。Provider Client Factory 已由 Composition Root 创建并在这些 LLM 适配器间共享，是放置进程内共享治理状态的合适位置。

本 Change 只治理 OpenAI-compatible 的 LLM 请求。Embedding 使用独立的 Gitee Provider，不在此范围；数据库、Conversation 与 HTTP/SSE 契约没有变化。

## Goals / Non-Goals

**Goals:**

- 以单个有效 Provider 配置为边界，限制每分钟实际请求数、短时突发量和同时在途的上游请求数。
- 让 Chat、流式 Chat、结构化调用和 RAG 的每一次 Provider 尝试共享同一治理状态。
- 将 resource 与 Coding Plan 的额度设置隔离，提供可按套餐调整的保守默认值和严格配置校验。
- 在等待、开始、释放和取消路径记录不含密钥、提示词或模型文本的治理日志。

**Non-Goals:**

- 不估算或扣减 token，也不读取资源包余额。
- 不做跨 Uvicorn worker、跨实例或 Redis 限流；多进程全局配额是独立 Change。
- 不实现熔断、自动 Provider 降级、排队状态 API 或前端配额展示。
- 不改变 `ChatLlmPort`、HTTP 请求、SSE 事件、Conversation 写入或数据库结构。

## Decisions

### 1. 以共享 Client Factory 为治理器所有者

`OpenAICompatibleClientFactory` 从基础设施层的进程内注册表取得一个 `LlmRequestGovernor`，并向它创建的 Chat、Structured 和 RAG 基础设施适配器注入该实例。注册表以完整有效 Provider 配置为键，因此逐 HTTP 请求创建的 Container 仍会共享同一份额度。治理器留在 `app/infrastructure/llm/`，Application、Domain、Ports 和 HTTP Schema 不感知其存在；Composition Root 继续只负责选择和组装。

另一种做法是在 HTTP 中间件限制所有请求。它无法覆盖 RAG、MCP、后台调用和同步结构化调用，也无法区分一次浏览器请求中的 Provider 重试，因此不采用。

### 2. 对每个真实 Provider 尝试同时执行令牌桶和并发租约

治理器以 `monotonic` 时钟维护每分钟补充的令牌桶。每次将要触发的上游请求都先取得一枚令牌，再取得一个并发租约；没有可用令牌或名额时以可取消的等待而非忙轮询处理。同步调用使用线程安全的阻塞路径，异步流式调用使用可取消的异步路径。令牌桶状态和并发计数受锁保护。

一个流式尝试从创建上游流开始持有租约，到流结束、关闭、异常或消费者断开时释放。首 activity 前的重试会释放旧租约，并在下一次尝试重新获取令牌与租约；首 activity 后既有的“不重试”规则不变。同步 Chat、结构化调用和 RAG 在每次 `retry_policy` 执行的实际函数调用外层取得租约。

将令牌按“用户请求”而非“尝试”扣除会让短暂失败后的重试绕过套餐限额，故不采用。令牌桶不会归还已取消但尚未发出 Provider 请求的令牌；先取得并发租约再取得令牌可避免这种取消窗口，并使待发送任务数量受控。

### 3. 将配额配置纳入有效 Provider Profile

新增不可变的请求治理配置，包含 `requests_per_minute`、`burst`、`max_concurrency`。GLM resource 与 Coding Plan 各自通过环境变量配置三项值；resource 默认采用 MVP 实测的保守 `30 RPM / burst 3 / concurrency 3`，Coding Plan 使用独立的保守默认值。DeepSeek 使用通用 LLM 请求治理配置，避免共享适配器存在无控制分支。所有值必须为正，`burst` 不得大于一分钟速率上限。

旧 `LLM_STREAM_MAX_CONCURRENCY` 只表达了已淘汰的 HTTP 特例，移除其应用语义并由有效 Provider 的 `max_concurrency` 完整取代。当前工程尚未上线，不提供旧变量兼容映射，避免旧流式限制意外影响同步调用。

### 4. 可观测性和错误语义保持克制

治理器仅记录 Provider、GLM Profile（如有）、阶段、等待时长和已配置限额。它不写入 API Key、输入、输出、余额或原始异常。调用因等待被取消时，不创建上游请求；其他上游错误仍由既有重试策略与安全错误映射处理。HTTP 层不再提前返回其私有的“流式并发上限” `429`，因此所有 LLM 调用具有一致的等待和错误语义。

## Risks / Trade-offs

- [单进程上限无法覆盖多个 worker 或实例] → 明确记录范围，并在扩容前单独引入外部共享限流器。
- [保守默认值可能降低峰值吞吐] → 将三个额度全部外置配置，并记录脱敏等待指标以支持依据套餐调整。
- [长流占用并发名额] → 这是防止资源包并发耗尽的预期行为；既有总时长、空闲和断连关闭机制仍负责回收。
- [同步调用在配额紧张时占用工作线程] → 当前同步 LLM 路径已是阻塞调用；后续若出现明显排队压力，再单独演进异步任务或队列。

## Migration Plan

1. 部署前在环境中按实际资源包填写 resource 的 RPM、burst 与并发上限；不填写时使用保守默认值。
2. 删除 `LLM_STREAM_MAX_CONCURRENCY`，改用所选 Profile 的 `*_REQUEST_MAX_CONCURRENCY`。
3. 先在 resource Profile 以少量真实流式请求验收，再在需要时切换到 Coding Plan Profile，其配额不会继承 resource 值。
4. 回滚代码后恢复旧部署配置；本 Change 不涉及数据库或持久化迁移。

## Open Questions

无。实际套餐限额由运行环境变量而非代码常量决定；当前默认值只作为安全起点。
