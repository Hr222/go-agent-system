## Why

当前的 `LLM_STREAM_MAX_CONCURRENCY` 只限制浏览器流式入口，结构化调用和重试尝试不会进入同一控制面。使用有速率限制的 GLM 资源包时，这会让并发峰值和重试叠加为 `429`，也无法按 resource 与 Coding Plan 的不同额度分别调节。

## What Changes

- 为共享的 OpenAI-compatible Provider Client 增加进程内请求治理：令牌桶速率限制和在途请求并发上限。
- 让普通 Chat、流式 Chat、结构化调用以及每一次实际的上游重试都经过同一个治理器；流式调用在连接关闭、失败或消费者取消后释放并发名额。
- 为 GLM resource 与 Coding Plan Profile 分别提供每分钟请求数、突发量和并发上限配置；资源包使用保守默认值，便于在不改代码的情况下按已购套餐调整。
- 用统一的上游并发限制替代仅覆盖 HTTP 流式入口的 `LLM_STREAM_MAX_CONCURRENCY`。
- 不改变已有 HTTP 请求或 SSE 事件契约；配额等待发生在服务端调用 Provider 之前。

## Capabilities

### New Capabilities

- `llm-request-governance`: 对 OpenAI-compatible 上游请求执行可配置的速率与并发治理。

### Modified Capabilities

- `glm-runtime-profiles`: GLM 的 resource 与 Coding Plan Profile 分别配置请求治理额度，并保持相互隔离。

## Impact

- 影响 `app/shared/config.py`、`app/infrastructure/llm/`、`app/composition/` 和流式 HTTP 入口的现有并发闸门。
- 新增运行时环境变量和脱敏治理日志；HTTP、数据库、前端与持久化结构不变。
- 治理器仅在单个应用进程内共享。跨进程全局限流、熔断和 Provider 自动降级不在本 Change 范围内。
