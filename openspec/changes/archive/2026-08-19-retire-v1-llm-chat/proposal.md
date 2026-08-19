## Why

`/api/v1/llm/chat` 及其 SSE 变体是 V1 为快速落地建立的无状态入口。V2 已具备统一的 `/api/v1/interaction/chat/stream` 路径、Gateway 识别与确认，以及 Conversation / Dialogue 能力；继续保留旧入口会形成绕过 Gateway 的后门，也会让前端保留两套不一致的对话协议。

## What Changes

- 删除旧 `/api/v1/llm/chat` 和 `/api/v1/llm/chat/stream` 路由注册及专用 HTTP Schema。
- 删除仅调用旧入口的前端 API、流式 Hook、类型和测试，Chat 页面继续使用 Interaction 流式入口。
- 删除只针对旧入口的后端 HTTP 测试及代理验收配置。
- 增加回归测试，明确旧地址返回 `404`，并验证 V2 Interaction 对话入口仍已注册。

## Non-Goals

- 不删除 `app/modules/llm`、`ChatApplication`、`StreamingChatApplication` 或 Provider 适配器；它们仍是 V2 对话、续写和其他能力的内部依赖。
- 不调整 Gateway、Conversation、Agent Runtime、认证授权或上传适配器。
- 不提供兼容重定向、开关或备用后门。

## Impact

- HTTP 客户端必须使用 V2 Interaction / Dialogue 路径；浏览器不得再调用旧 LLM HTTP 地址。
- 这是受控的不兼容删除，但与已经完成的 V2 前端路径一致。
