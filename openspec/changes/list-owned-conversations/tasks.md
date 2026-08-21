## 1. 主体范围摘要查询

- [ ] 1.1 定义 Conversation summary read model、owner-scoped Port 与 PostgreSQL 查询，按更新时间和稳定游标分页。
- [ ] 1.2 添加 `GET /api/v1/conversations` 的 HTTP schema、assembler、route 与 Access/Principal 依赖。

## 2. 验证

- [ ] 2.1 覆盖主体过滤、排序、游标、空列表和不泄露消息正文的仓储/HTTP 测试。
- [ ] 2.2 运行相关 pytest 和 OpenSpec 严格校验。
