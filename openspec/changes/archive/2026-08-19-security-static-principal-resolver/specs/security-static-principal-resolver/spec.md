## ADDED Requirements

### Requirement: 服务端静态主体解析

系统 MUST 支持由服务端构造一个固定的 `RequestPrincipal`，包含非空主体标识、固定权限集合和 `authenticated=true`。

#### Scenario: 解析配置主体
- **WHEN** 使用合法主体标识和权限集合构造静态 Resolver 并解析任意请求上下文
- **THEN** 系统返回配置的主体和权限
- **AND** 多次解析结果保持一致

#### Scenario: 静态解析不信任客户端权限
- **WHEN** 请求上下文包含 `x-permissions` 或其他客户端权限字段
- **THEN** 系统仍只返回服务端构造的权限集合

