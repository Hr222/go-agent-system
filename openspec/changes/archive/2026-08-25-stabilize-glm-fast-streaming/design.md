## Context

上一个 GLM Profile Change 已将资源包与 Coding Plan 的端点、模型和预算隔离，但 `LlmProviderConfig.thinking` 只由 DeepSeek 设置。GLM 的 Chat、流式 Chat、结构化调用和 RAG 调用因此会省略 `thinking` 请求体，行为依赖上游默认值。

普通 Chat 流的首段等待目前仅在获得非空 `content` 后解除。GLM 可能先发送 `reasoning_content`，此时上游实际持续工作，但浏览器仍会在首段超时前得不到 `meta`。推理文本属于 Provider 内部数据，不能进入 Chat LLM Port 的文本内容、Conversation 或 SSE。

## Goals / Non-Goals

**Goals:**

- 为 GLM 两个运行 Profile 明确定义可独立覆盖的 thinking 模式，并让所有既有 GLM Chat Completion 调用显式使用它。
- 用 Provider 中立的活动标记传递“上游已经产生事件”这一事实，首段等待据此解除。
- 保留前端 SSE 契约、Conversation 写入规则和现有的总时长、空闲超时与取消语义。

**Non-Goals:**

- 不把 reasoning 正文返回给客户端、写入日志或写入数据库。
- 不实现 AsyncOpenAI 显式注入、SDK/应用重试、限流、熔断、结构化伪流式聚合或路径级输出预算。
- 不修改会话历史装配、数据库结构、HTTP Schema、前端和 Provider 选择机制。

## Decisions

### thinking 是 GLM Profile 配置的一部分

新增 `ZHIPU_RESOURCE_THINKING` 与 `ZHIPU_CODING_THINKING`。资源包默认 `disabled`，以当前普通 Chat 的低延迟为优先；Coding Plan 默认 `low`，避免对 `glm-5.3` 使用其在标准端点不支持的 `disabled`。允许的值由服务端配置校验为 `disabled`、`enabled`、`low`、`high`、`max`，不由 HTTP 请求或模型结果决定。

`LlmProviderConfig` 持有已选择的模式，现有 OpenAI-compatible Chat、Structured 与 RAG 适配器继续通过该中立配置组装 `extra_body`。不为每个应用用例建立 GLM 专属参数，避免把 Provider 语义渗入 Application 或 HTTP 层。

### 活动标记只传递生命体征，不传递 reasoning

在 `ChatLlmStreamChunk` 增加布尔活动标记。GLM Adapter 在 Provider chunk 有可展示正文或 reasoning 内容时标记活动，但只把可展示正文放入 `content`。Streaming Conversation 原样转发 chunk；Interaction 在首段阶段接受第一个活动 chunk，先输出既有 `meta`，且仅在 `content` 非空时输出 `delta`。

将 reasoning 当作正文会泄漏内部信息，也会污染 assistant Message；继续只检查正文会错误地把活动中的 Provider 判断为超时。布尔标记提供了最小的跨层事实，不改变文本 Port 的语义。

### 保持现有首段超时变量并更正其语义

继续使用 `LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS`，避免本 Change 造成部署配置名称迁移；其语义改为“首个上游活动超时”。环境变量与 `.env.example` 说明同步更新。总时长和空闲时长仍按现有规则计算，不以 reasoning 或正文内容改变。

## Risks / Trade-offs

- [个别模型或端点不支持所选 thinking 值] → 两个 Profile 均保留独立环境变量覆盖，并以资源包和 Coding Plan 的受控冒烟验证配置。
- [LangChain 在不同 Provider 版本中存放 reasoning 字段的位置不同] → 适配器仅识别已知的响应属性和元数据映射；无法识别时维持旧的正文首段行为，不推测或输出字段。
- [`meta` 早于第一段可展示正文] → 这是正常的上游已活动信号；SSE 事件和浏览器安全字段不变，前端仍只渲染 `delta.content`。
- [长输出仍触发总时长] → 总预算与输出上限的联动不属于本 Change，保持现有受控失败语义。

## Migration Plan

1. 部署时补充两个 GLM thinking 环境变量，默认资源包使用 `disabled`、Coding Plan 使用 `low`。
2. 分别对资源包和 Coding Plan 执行最小文本冒烟，确认请求可完成且无 reasoning 泄漏。
3. 若某 Profile 的模型不支持默认值，仅修改其对应 `ZHIPU_*_THINKING` 后重启服务；不需数据库迁移或回滚代码。
4. 回滚时移除新变量并回退本 Change；流式和 Conversation 已有事实不受影响。

## Open Questions

无阻塞问题。后续会单独评估按调用路径细分模型、输出预算和 total timeout。
