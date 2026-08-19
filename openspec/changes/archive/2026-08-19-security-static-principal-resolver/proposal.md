## Why

当前 HTTP 安全边界只有匿名解析器，无法在不建立用户模块的前提下验证受保护 Agent 的完整调用链。需要一个仅由服务端构造的静态主体实现，作为后续认证适配的过渡测试替身。

## What Changes

- 新增可配置主体和权限的 `StaticPrincipalResolver`。
- Resolver 不读取客户端提交的权限 Header。
- 保持现有匿名 Resolver 和 HTTP 默认行为不变。

## Capabilities

### New Capabilities

- `security-static-principal-resolver`: 解析服务端固定主体和权限集合。

### Modified Capabilities

- 无。

## Impact

影响 security domain/port 及其单元测试；不修改 HTTP 契约、数据库、Agent Runtime 或默认安全行为。

