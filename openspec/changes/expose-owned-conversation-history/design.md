## Context

ConversationHistoryReadService 已提供有序、游标分页的只读能力，但没有浏览器适配层。Conversation Access 将在读取前验证主体归属。

## Goals / Non-Goals

**Goals:** 对当前主体开放单一会话的消息页和最小元数据。

**Non-Goals:** 不返回 Event、Agent 原始结果、完整模型上下文或写入能力。

## Decisions

- 使用 `GET /api/v1/conversations/{conversation_id}/messages?limit=&after_sequence=`；复用现有顺序游标语义。
- Route 先通过 Access 解析会话，再调用只读历史服务；HTTP 响应只投影 Message 的 UUID、role、content、sequence、created_at。
- 访问拒绝统一为受控 not-found 类响应，不暴露 owner 差异。

## Risks / Trade-offs

- [大历史响应] → 维持 1-200 页大小和 cursor，不返回完整会话。
