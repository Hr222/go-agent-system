## Why

P3.1 已经能够在 Conversation 中完成一次经用户确认的 Agent 调用，并持久化 `agent_call` 与 `agent_result`。但调用完成后页面只能看到结构化结果摘要，不能在同一轮对话中得到自然、连续的助手回复，用户需要自行理解内部结果。

现在需要把已持久化的 Agent 结果交给 Dialogue Runtime 进行一次受控续写，让 Conversation 最终形成可读的 assistant Message，同时保留 Agent 事件作为可追溯事实。

## What Changes

- 新增 Agent 结果续写应用能力：读取指定 Conversation 的历史消息和关联 Agent 结果，构建包含结果的模型上下文。
- 使用现有 Conversation Context Builder 和 Chat LLM Port 生成最终助手回复，并将非空回复持久化为 assistant Message。
- 续写失败时保留已有用户消息与 Agent 事件，不写入空的或伪造的 assistant Message，返回稳定错误状态。
- 让 P3.1 的 Agent 调用完成结果可以显式触发续写；不新增绕过 Gateway 的 Agent 入口，不实现多 Agent、Workflow、Task Management 或 Harness。
- 保持 Agent 结果投影的安全边界，不把原始文件字节、Provider 响应、权限和异常堆栈送入续写上下文。

## Capabilities

### New Capabilities

- `dialogue-agent-continuation`: 将已完成的单次 Agent 结果安全注入 Conversation 上下文并生成最终 assistant Message。

### Modified Capabilities

- `dialogue-agent-invocation`: Agent 调用完成后允许由上层显式触发续写；调用服务本身仍只负责 Agent 事件和结果摘要持久化。

## Impact

- 影响 `app/modules/dialogue/application/`、Conversation Context Builder、Chat LLM Port 以及 Composition Root 的组装代码。
- 增加 Dialogue 应用层的内部结果契约和测试；不新增公开 HTTP 路由，不改变客户端提交的能力授权字段。
- 读取 PostgreSQL 中已有 Conversation Message/Event 数据；不新增表，不引入 Redis 或新的 Provider。
- 续写会再次调用配置的 Chat LLM Provider，需沿用现有模型、Prompt 版本、Token 元数据和错误映射边界。
