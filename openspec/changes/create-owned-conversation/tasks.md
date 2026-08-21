## 1. 创建 HTTP 契约

- [x] 1.1 添加创建空 Conversation 的 request/response schema、route、assembler 与依赖注入，只调用 Conversation Access。
- [x] 1.2 在 Composition Root 组装创建用例，确保请求不能提交 owner、消息或模型参数。

## 2. 验证

- [x] 2.1 覆盖创建成功、主体缺失、响应字段和无 Message 副作用的 HTTP 测试。
- [x] 2.2 运行相关 pytest 和 OpenSpec 严格校验。
