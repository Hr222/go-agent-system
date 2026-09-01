## Why

真实浏览器验证发现，普通多轮对话的自然追问可能被能力意图识别返回为 `unrecognized`，因而在进入 Conversation Runtime 前终止。用户必须改写为明确的“通用 LLM”请求才能继续对话，这破坏了普通 Chat 的多轮体验。

## What Changes

- 为已完成候选检索、但识别结果为 `unrecognized` 的有效 Chat 输入增加服务端 `chat.general` 兜底分流。
- 兜底路径必须重新读取能力目录、验证当前主体可用性、`never` 确认策略、固定分发绑定和输入契约，再进入既有流式 Conversation Runtime。
- 保持业务能力的候选识别、资料澄清和显式确认逻辑；`needs_clarification`、目录或索引不可用不得降级为通用 Chat。
- 增加 Gateway、SSE 以及前端实际多轮行为的回归验证，确保自然追问流式完成并持久化。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `risk-tiered-chat-interaction`: 识别为 `unrecognized` 的低风险普通输入在受控校验后可回退到 `chat.general`；业务澄清和不可用状态保持原分支。
- `streaming-conversation-interaction-adapter`: 由通用 Chat 兜底授权的请求也必须进入既有 Conversation Runtime 并保留 SSE 与历史恢复契约。

## Impact

- 影响 `app/platform/interaction/application/gateway.py` 的授权决策，以及对应交互和流式测试。
- 不变更 HTTP 路径、SSE 字段、数据库结构、Provider 配置或业务 Agent 执行权限。
