## Context

同步 Dialogue 已验证了 Conversation + ContextBuilder 逻辑；前序流式 Conversation Runtime 已拥有普通 Chat 的会话创建、消息事实与失败闭合。普通 Chat 只需为这一条流式链路适配异步 `StreamingChatLlmPort` 的历史请求构造；HTTP/SSE 应保留在 Interaction 之外。

## Goals / Non-Goals

**Goals:** 在 Dialogue 层为既有流式 Conversation Runtime 实现流式历史上下文，同时保留既有消息时序。

**Non-Goals:** 不注册 HTTP 路由、不产生 SSE、不中断 Agent 链路、不做摘要/缓存，也不新增平行的流式会话运行时。

## Decisions

- 扩展前序流式 Conversation Runtime 的请求构造，接入 history reader 与 context builder；不得重新实现会话创建、Access、user/assistant 写入或失败闭合。
- 保持既有的先写 user Message、完成时才写 assistant Message 的时序；在两者之间分页获取历史、构建 ModelContext，并把当前用户消息仅作为 `user_prompt`，其余消息映射为 history。
- 普通 Chat 仍只有一个流式运行时；调用方终止或 provider error 时沿用既有的不写部分 assistant Message 语义。

## Risks / Trade-offs

- [流已输出但持久化失败] → 返回受控终态；前端不将未持久化文本当作历史事实。
- [上下文 Change 重复实现运行时] → C1 只扩展 H1 的请求构造与依赖，复用其消息事实与失败语义。
