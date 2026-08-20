## 1. HTTP 装配

- [x] 1.1 在 HTTP Security Adapter 中按配置选择 Anonymous 或 Static Resolver。
- [x] 1.2 保留 `get_request_principal` 的依赖覆盖和请求上下文传递契约。

## 2. 集成验证

- [x] 2.1 增加 anonymous/static 模式的 HTTP 依赖注入测试。
- [x] 2.2 验证伪造权限 Header 不改变主体，并运行 Interaction HTTP 回归测试。
