## 1. 历史查询 HTTP 适配

- [x] 1.1 定义只读消息页 response schema、assembler 与 `GET /api/v1/conversations/{conversation_id}/messages` 路由。
- [x] 1.2 在读取前接入 Conversation Access，并复用现有 limit/after_sequence 校验与分页结果。

## 2. 验证

- [x] 2.1 覆盖首页、游标续读、空会话、越权拒绝和响应不含事件/上下文的 HTTP 测试。
- [x] 2.2 运行相关 pytest 和 OpenSpec 严格校验。
