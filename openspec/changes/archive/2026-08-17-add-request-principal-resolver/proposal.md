## Why

平台能力目录已经能声明某项能力需要的权限，但项目尚未有用户管理或认证模块，统一交互入口若直接信任客户端提交的权限字段，会产生越权调用 Agent 的风险。需要先提供一个可替换的服务端请求主体解析边界，使后续认证实现能够接入而不改写能力目录和交互流程。

## What Changes

- 新增请求主体值对象和 `PrincipalResolver` 端口，表达服务端已验证的主体标识与权限集合。
- 新增匿名默认实现和 HTTP 适配依赖；当前未认证请求固定获得空权限，不读取客户端自报的权限或角色。
- 更新架构文档，明确能力目录的权限声明与请求主体解析职责分离。
- 增加替换性与默认拒绝的测试，为后续 JWT、Session 或 SSO 适配器保留稳定插口。

## Capabilities

### New Capabilities

- `request-principal-resolution`: 在 HTTP 适配层将可信认证结果转换为应用层可消费的请求主体和权限集合。

### Modified Capabilities

- 无。

## Impact

- 新增 `modules/security` 的轻量领域值对象与端口，以及 `interfaces/http` 的匿名适配器。
- 不新增用户表、登录接口、JWT、Session、SSO、角色管理、数据库迁移或前端账号页面。
- 不改变既有 HTTP 业务接口；后续统一交互入口通过该插口读取权限，受保护能力在匿名状态下默认不可用。
