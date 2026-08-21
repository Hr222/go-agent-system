## 1. Access 应用边界

- [x] 1.1 定义 owner-scoped Conversation Access command/query/port，并以可信 `RequestPrincipal.subject` 创建或解析会话。
- [x] 1.2 将 Conversation Repository 查询和相关 Dialogue/Agent 组装入口迁移为通过 Access 使用会话。

## 2. 验证

- [x] 2.1 覆盖同主体访问、跨主体拒绝、主体缺失和拒绝路径零读写的测试。
- [x] 2.2 运行相关 pytest、依赖边界检查和 OpenSpec 严格校验。
