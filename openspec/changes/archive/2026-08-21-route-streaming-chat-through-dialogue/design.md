## Context

Interaction 已负责识别、授权和浏览器 SSE。既有流式 Conversation Runtime 负责会话事实，C1 在其上补充模型上下文；两者应通过同一个应用契约连接，而不是让 Interaction 读写仓储或保留第二条普通 Chat 路由。

## Goals / Non-Goals

**Goals:** 让普通 Chat 的既有接入点使用上下文增强的流式 Conversation Runtime，并安全传播 Conversation 标识。

**Non-Goals:** 不改变 HTTP URL、请求 JSON、Agent 确认、前端状态或 Provider 适配，也不新增第二个普通 Chat 流式分支。

## Decisions

- 用上下文增强运行时替换 `chat.general` 的既有 H1 流式运行时依赖；同一普通请求只进入这一条分支，其它 capability 分支保持不变。
- `meta` 在会话已准入、user Message 已写入、Context 已建成后发出，携带服务端 Conversation ID。
- Dialogue 内部错误在 SSE 开始前/后按现有 controlled error 语义映射，不改变错误中的敏感信息约束。

## Risks / Trade-offs

- [Interaction 和 Dialogue 双重写消息] → 以同一上下文增强运行时替换 H1 依赖，不保留平行普通 Chat 分支；单元测试验证每轮只有该运行时写入事实。
