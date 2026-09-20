## 1. 独立 Tender Task Worker

- [x] 1.1（对应 `task-worker-execution`：独立运行入口）增加受配置约束的 Tender Worker 循环与显式运行命令；完成条件：HTTP 生命周期不启动 Worker，独立入口只组装固定 Tender Executor，并在恢复、重试和执行阶段后关闭资源。
- [x] 1.2（对应 `task-worker-execution`：运行资源隔离）为 Worker 循环增加正常空轮询、阶段失败继续、停止信号和每阶段独立 Session 的自动化测试；完成条件：测试证明不会复用失败的持久化对象或从运行参数选择任意执行器。

## 2. Dialogue 异步交接

- [x] 2.1（对应 `dialogue-agent-invocation`：异步接收状态）让 Invocation、Agent Turn、Gateway Response 与 HTTP Schema 保留 `accepted` 状态和安全 execution reference；完成条件：确认内部异步调用返回 `accepted`，不再映射成 `failed`。
- [x] 2.2（对应 `dialogue-agent-invocation`：异步接收状态写入事件）记录带 execution reference 的 `agent_call` 接收事件，并保持无 `agent_result`、`agent_error` 或 assistant Message；完成条件：自动化测试覆盖事件内容和敏感字段排除。
- [x] 2.3（对应 `dialogue-agent-gateway-integration`：Chat 已接收状态）补充 Chat 确认与 HTTP 回归测试；完成条件：响应可安全表达 `accepted`，同步完成、取消和失败语义不回退。

## 3. 文档与验证

- [x] 3.1 同步 `ARCHITECTURE.md`、系统看板、README 和 `.env.example`；完成条件：文档区分独立 Worker、内部异步交接、外部 MCP 同步以及仍未实现的 Workflow/下载/终态会话回传。
- [x] 3.2 运行相关 Task、Dialogue、Interaction、Tender 和架构测试，再运行全量后端、lint、编译、OpenSpec 严格校验及差异检查；完成条件：记录通过结果，不将外部 Provider 或浏览器 E2E 伪称为已验收。
