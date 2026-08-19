## 1. Gateway 与对话应用边界

- [x] 1.1 为 Gateway 增加只消费并重新校验确认提议的 Agent 确认契约，确认成功返回 `ApprovedCapabilityDispatch` 且不执行分发；补充单元测试证明不会调用运行时。
- [x] 1.2 让 Chat 流在识别到待确认 Agent 能力时创建 Conversation、写入待确认 `agent_call` 事件，并以提议标识安全绑定调用上下文；补充应用层测试。
- [x] 1.3 让 Chat 确认接口在 Gateway 确认后调用 Dialogue Agent Invocation，处理完成、取消、提议失效和失败状态；补充 HTTP 测试。

## 2. 删除绕过入口并接入页面

- [x] 2.1 删除独立 Agent Invocation 路由、schema、依赖和进程内直达调用存储，确认不再存在浏览器直传能力代码的 HTTP 执行入口。
- [x] 2.2 删除独立 Agent 调用页面、前端 API、Hook、路由和导航项；Chat 页面消费同一对话内的确认结果摘要与 Conversation 标识。
- [x] 2.3 补充前端 Chat 测试，覆盖 Agent 确认卡片、确认完成摘要和取消状态。

## 3. 验证

- [x] 3.1 运行受影响后端测试、前端测试与前端构建，验证正常 Chat 和非 Agent 确认路径未回归。
- [x] 3.2 运行 Ruff 和 OpenSpec 严格校验，记录与本 Change 无关的既有问题（如有）。

## 4. 验证记录

- 后端全量测试通过：`python -m pytest -q`，396 项通过；仅有 FastAPI `TestClient` 的第三方弃用警告。
- 前端单进程测试通过：28 项通过；生产构建通过。默认并行运行 Vitest 时出现过本机 Node 工作进程内存不足，单进程运行没有断言失败。
- `ruff check app` 与本 Change 覆盖的测试文件通过。执行全量 `ruff check app tests` 时仍有 3 个既有问题：`tests/agent/tender/test_prompts.py` 的导入排序，以及 `tests/application/test_knowledge_management_http.py` 的未使用导入和超长行；本 Change 未修改这些文件。
- `openspec validate dialogue-agent-gateway-integration --type change --strict` 通过。
