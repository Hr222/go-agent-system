## Context

Conversation Access 可创建空会话，但浏览器还没有稳定 HTTP 入口取得会话 ID。

## Goals / Non-Goals

**Goals:** 提供主体范围内的新建空会话 API，作为新建对话和上传前绑定的基础。

**Non-Goals:** 不发送首条消息、不调用 LLM、不列出或读取历史。

## Decisions

- 使用 `POST /api/v1/conversations`，返回 `201` 和最小 Conversation 元数据。
- Route 只注入 Principal 并调用 Access；HTTP Schema 不进入 Domain。
- 没有主体时返回受控拒绝，客户端不提供 owner。

## Risks / Trade-offs

- [产生从未使用的空会话] → 接受该可追溯状态；不在本 Change 中做自动清理策略。
