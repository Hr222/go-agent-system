## Context

Conversation 已有持久化但没有主体归属。当前 `RequestPrincipal` 可由静态 resolver 提供稳定 Mock `subject`。

## Goals / Non-Goals

**Goals:** 将非空、不透明的 `owner_subject` 保存为 Conversation 事实，并只从可信主体取得。

**Non-Goals:** 不实现会话访问拦截、HTTP、真实用户或权限。

## Decisions

- `owner_subject` 归 Conversation Domain，不归 Dialogue 或 HTTP；它是资源归属而非显示名。
- ORM 和 SQL 将其设为非空并建立 owner 查询索引。新会话构造器显式接收该值。
- 迁移先使用部署配置的受控迁移主体回填已有开发数据，再加非空约束；无法确认归属的记录不自动分配给真实主体。

## Risks / Trade-offs

- [历史数据错误归属] → 迁移前报告未归属记录，使用显式迁移参数或停止迁移。
- [匿名主体无法归属] → 由后续 Access Change 决定拒绝持久化会话。
