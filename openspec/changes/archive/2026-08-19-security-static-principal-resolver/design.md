## Context

`PrincipalResolverPort` 已定义可信主体解析边界，当前只有忽略请求上下文的匿名实现。本 Change 只补充一个可注入的静态实现，不引入用户、会话或令牌系统。

## Goals / Non-Goals

**Goals:**

- 返回稳定的 `subject`、权限集合和认证状态。
- 让权限链路可以在本地和集成测试中被真实调用。

**Non-Goals:**

- 不解析浏览器 Header。
- 不实现登录、用户存储、JWT 或多用户隔离。

## Decisions

- 使用不可变配置构造 Resolver，而不是在 `resolve` 中读取请求字段；这样客户端不能自我授予权限。
- 实现放在 security port 的适配器边界，继续满足 HTTP 与应用层解耦。
- 权限使用 `frozenset[str]`，复用 `RequestPrincipal.permission_tuple()` 的规范化行为。

## Risks / Trade-offs

- [静态主体被误用于生产] -> 默认不改变匿名实现，并在后续配置 Change 中显式启用。
- [测试主体跨请求共享] -> 文档明确其仅适用于单操作者或测试环境。

## Migration Plan

无迁移；本 Change 默认不改变运行时行为。

## Open Questions

配置名称和启用方式留给后续配置 Change 决定。

