## Why

Resolver 端口和配置完成后仍需要在 HTTP Composition 边界完成选择，否则配置不会影响真实 Interaction 请求。这个 Change 只改变适配器装配，不改变应用层权限逻辑。

## What Changes

- 让 `get_principal_resolver()` 根据主体模式返回匿名或静态 Resolver。
- 保持请求上下文只作为 Resolver 输入，不允许客户端覆盖权限。
- 增加 HTTP 依赖注入测试。

## Capabilities

### New Capabilities

- `security-http-principal-binding`: 将配置主体模式绑定到 HTTP 请求主体。

### Modified Capabilities

- 无。

## Impact

影响 `app/interfaces/http/security.py` 和 HTTP security 测试；anonymous 默认路径、业务 Gateway、数据库和前端契约不变。

