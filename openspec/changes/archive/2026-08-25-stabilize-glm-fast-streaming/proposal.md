## Why

GLM 已经可在资源包和 Coding Plan 间独立选择，但正常对话仍依赖 Provider 默认的 thinking 行为。流式首包等待又只把可展示正文视为活动，GLM 在输出 reasoning 时会被误判为超时，导致用户看到失败而非受控的持续生成。

## What Changes

- 为 GLM 的 `resource`、`coding_plan` Profile 各自增加服务端 thinking 配置，并在 Chat、流式 Chat、结构化调用和 RAG 调用中显式传递。
- 将资源包 Profile 的默认策略设为关闭 thinking，Coding Plan Profile 的默认策略设为低档 thinking；仍允许仅由服务端环境变量按模型与端点覆盖。
- 为流式 LLM Port 增加不含 reasoning 正文的“上游已活动”标记；普通 Chat 的首段等待以该标记为准，收到 reasoning 活动即可开始 SSE 会话，不向浏览器或 Conversation 写入 reasoning。
- 保留既有 SSE 事件名称、HTTP 请求/响应、Conversation 持久化、总时长与空闲超时语义。

## Capabilities

### New Capabilities

- `glm-fast-streaming`: 定义 GLM 显式 thinking 策略和普通 Chat 流式首个上游活动的受控处理。

### Modified Capabilities

- `glm-runtime-profiles`: 将 thinking 策略纳入资源包与 Coding Plan 的独立运行配置。
- `streaming-conversation-interaction-adapter`: 将普通 Chat 首段等待改为识别上游活动，而非只识别可展示正文。

## Impact

- 影响 `Settings`、Provider 配置、OpenAI-compatible 适配器、流式 LLM 契约和 Interaction Chat 流适配。
- 不修改 HTTP 契约、前端、数据库、Conversation 消息内容或持久化模型；内部 reasoning 绝不进入 SSE、日志或数据库。
- 影响 GLM 外部请求体：新增显式 `thinking` 参数。Profile 配置不从客户端请求读取，敏感信息仍不记录。
- 不包含 SDK 异步客户端、重试、限流、非流式结构化流聚合或上下文预算改造；这些需要独立 Change。
