## Why

当前 P3.1 的页面提供了独立 Agent 调用入口，浏览器可以直接提交 `capability_code` 和业务输入。这绕过了统一交互 Gateway 的自然语言意图识别，导致确认卡片失去意义，也让对话页面无法成为 Agent 调用的真实入口。现在需要在继续扩展对话能力前纠正这条边界。

## What Changes

- 将 Agent 调用接入现有 Chat 对话流：用户提交自然语言和可选附件等原始上下文，Gateway 负责识别能力、校验权限和生成待确认提议。
- 在对话流中返回 Agent 待确认事件，并复用现有确认卡片完成确认或取消。
- 确认请求由 Gateway 一次消费提议，只产出服务端生成的 `ApprovedCapabilityDispatch`；Dialogue Invocation 负责把批准后的调用写入 Conversation 事件并调用 P2.6 Dispatcher。
- 移除独立的 `/dialogue/agent-invocations` HTTP 路由、对应前端页面和导航入口，避免形成绕过 Gateway 的后门。**BREAKING**
- 保留 Agent 结果事件和安全摘要；不在本 Change 中让 LLM 根据 Agent 结果生成最终自然语言回复。

## Capabilities

### New Capabilities

- `dialogue-agent-gateway-integration`: 在正常 Chat 对话中通过意图识别、用户确认和受控分发完成一次 Agent 调用。

### Modified Capabilities

- `llm-intent-recognition-gateway`: Chat 对话成为 Agent 意图识别和确认的唯一页面入口；确认后返回批准分发对象而不是在 Gateway 内直接执行。
- `dialogue-agent-invocation`: Invocation 服务消费 Gateway 已批准的分发对象，并把调用生命周期关联到对话事件。

## Impact

- 后端：交互 Gateway、Chat SSE 应用、Dialogue Invocation 组装和 HTTP 路由。
- 前端：Chat 页的确认结果处理；删除独立 Agent 调用页、API、Hook、路由和导航项。
- HTTP 契约：移除 `/dialogue/agent-invocations` 及其确认接口；Chat `/api/v1/interaction/chat/stream` 承载 Agent 待确认事件。
- 持久化：继续使用现有 Conversation 消息和事件表，无新增数据库或 Redis 依赖。
- 安全：客户端不再能够通过请求体指定能力代码、分发键或批准对象；用户附件等原始上下文仍必须经 Gateway 与目录校验后才能进入调用输入。
