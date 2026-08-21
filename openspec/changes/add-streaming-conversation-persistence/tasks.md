## 1. 流式 Conversation 运行时

- [ ] 1.1 定义不依赖 HTTP 的 Streaming Conversation command、事件/终态结果和 Access/写入/LLM 依赖。
- [ ] 1.2 实现创建或解析会话、先写 user、流式调用和正常完成后一次性写 assistant。
- [ ] 1.3 实现取消、断开、上游、空回答和写入失败时不写 assistant 的失败闭合。

## 2. 验证

- [ ] 2.1 使用替身覆盖新建、续写、消息顺序、完整成功与部分失败的 Dialogue 测试。
- [ ] 2.2 运行相关 pytest、架构边界检查和 OpenSpec 严格校验。
