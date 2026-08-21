## Context

owner 字段提供事实，但每条读写链路仍可能只按 UUID 查询。Access 必须成为 Conversation 对外使用前的统一应用边界。

## Goals / Non-Goals

**Goals:** 用 `RequestPrincipal.subject + conversation_id` 解析可访问会话，并隐藏不存在与跨主体访问的差异。

**Non-Goals:** 不增加 HTTP 路由、用户表、RBAC 或附件重构。

## Decisions

- 新增 Conversation Access 应用服务和 owner-scoped Port；Dialogue/HTTP 只获得已准入 Conversation。
- `subject` 缺失时拒绝创建或解析持久化 Conversation；不把匿名请求共享到一个公共 owner。
- 外部可观察的拒绝不区分会话不存在和非 owner，以减少枚举泄露。

## Risks / Trade-offs

- [遗留调用绕过 Access] → 将既有 Conversation 使用点迁移至 Access，并用依赖/行为测试覆盖。
