## Context

Interaction 已负责授权和 SSE，Streaming Conversation Runtime 负责会话事实和模型调用。二者通过应用契约连接。

## Goals / Non-Goals

**Goals:** 使浏览器普通 Chat 产生可恢复历史并获得会话标识。

**Non-Goals:** 不构建上下文、不改 Agent 分支、不加载历史 UI。

## Decisions

- 只替换已授权 `chat.general` 分支；Agent 确认维持现有逻辑。
- `meta` 在会话创建/访问及 user 写入后发出，携带 `conversation_id`；其它事件保持兼容。
- Runtime 错误映射成当前浏览器安全 SSE 错误，不能返回内部持久化或主体信息。

## Risks / Trade-offs

- [普通对话已有未保存响应] → 从部署后新请求开始形成历史，不尝试追补浏览器内存内容。
