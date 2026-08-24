## Context

会话详情读取按 ID 工作，Chat 侧栏还需要轻量摘要发现当前主体的会话。

## Goals / Non-Goals

**Goals:** 按 owner 查询、游标分页并返回最小摘要。

**Non-Goals:** 不搜索消息、不生成标题、不返回消息正文或修改会话。

## Decisions

- 在 Conversation Read Port 增加 owner-scoped summary list query，并按 `(updated_at DESC, id DESC)` 形成稳定游标。
- 使用 `GET /api/v1/conversations` 返回 id、created_at、updated_at；前端标题暂时从首条用户消息或固定文案派生，不保存生成标题。
- 请求主体缺失返回受控拒绝。

## Risks / Trade-offs

- [摘要没有可读标题] → 本 Change 只解决发现与排序，标题策略留给独立 Change。
