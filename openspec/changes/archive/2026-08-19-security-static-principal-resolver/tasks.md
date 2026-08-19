## 1. 静态主体实现

- [x] 1.1 实现可由主体和权限构造、固定为已认证状态的 `StaticPrincipalResolver`。
- [x] 1.2 为合法配置、空主体和客户端权限 Header 场景补充单元测试。

## 2. 回归验证

- [x] 2.1 验证 `AnonymousPrincipalResolver` 及现有 principal 测试保持通过。
- [x] 2.2 运行 security 测试并记录结果：`tests/security` 9 passed。
