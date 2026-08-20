## Context

当前 `get_principal_resolver()` 每次返回 `AnonymousPrincipalResolver`。它是明确的 HTTP 适配器插口，最小改动是只在此处选择已构造的 Resolver。

## Goals / Non-Goals

**Goals:**

- 使配置模式在真实 FastAPI Depends 链路中生效。
- 保留依赖覆盖能力，便于测试替身注入。

**Non-Goals:**

- 不修改 Gateway 或能力目录的权限算法。
- 不从请求 Header 解析权限。

## Decisions

- 选择逻辑留在 HTTP adapter，不把 `Settings` 传入应用模块。
- Resolver 可缓存为进程级实例；主体配置在进程启动时固定。
- anonymous 分支继续返回现有实现，保证无配置回归。

## Risks / Trade-offs

- [配置热更新不生效] -> 配置是进程启动配置，变更后重启服务；避免请求间主体漂移。
- [静态主体误暴露] -> 仅服务端配置生效，HTTP Header 仍被忽略。

## Migration Plan

先以 anonymous 部署，验证后在受控环境显式切换 static；回滚只需恢复 anonymous。

## Open Questions

正式认证适配器接入时可替换同一依赖函数，不改变路由签名。

