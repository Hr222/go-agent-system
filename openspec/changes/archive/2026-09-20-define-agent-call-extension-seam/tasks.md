## 1. 执行策略契约

- [x] 1.1 为已授权 Agent 调用定义平台内部的执行策略 Port、调用上下文和协议无关结果类型；完成条件：契约能表达同步完成、受控失败和未来延迟引用，且不依赖 HTTP、MCP、Task、ORM 或 Provider SDK。
- [x] 1.2 增加现有 `AgentRuntimePort` 的同步策略适配器；完成条件：能力代码、服务端固定 `dispatch_key`、标准化输入、主体权限和调用关联字段均能传入当前 Runtime，默认路径仍只调用一次 Runtime。

## 2. Dispatcher 与组装改造

- [x] 2.1 调整 `AgentCallDispatcher` 在策略授权和目录复核之后调用注入的执行策略；完成条件：授权失败时策略不被调用，授权成功时仍返回现有 `AgentCallResult` 或 `AgentCallError`，附件暂存与补偿行为不变。
- [x] 2.2 在 Composition Root 固定组装同步策略，并拒绝从目录、客户端输入或协议参数选择执行策略；完成条件：生产构造路径只有显式绑定，代码中不存在动态导入、远程执行地址或运行时任意注册。
- [x] 2.3 保留 `StructuredAgentCall` 的 `call_id`、`run_id`、`parent_run_id`、`conversation_id` 和 `turn_id` 关联字段；完成条件：成功和失败结果可按原调用字段关联，当前实现不创建父子树、不创建 Task。

## 3. 测试与边界验证

- [x] 3.1 扩展 Agent 分发单元测试；完成条件：覆盖默认同步成功、运行时失败、策略拒绝、目录失效、策略未配置、非法输出和替身策略注入场景。
- [x] 3.2 增加策略契约和安全结果测试；完成条件：验证策略不能绕过服务端 `dispatch_key`、权限和输入校验，且结果不泄漏异常堆栈、Provider 原文、凭据或原始二进制。
- [x] 3.3 执行相关后端 pytest、架构边界测试、`ruff check app tests`、`python -m compileall -q app tests`、`git diff --check` 和 `openspec validate "define-agent-call-extension-seam" --strict`；完成条件：命令结果成功并记录未覆盖的外部 MCP/Provider 人工验收项。

验证记录：全量后端测试 `767 passed`，另有 2 个既有弃用警告；架构边界测试 `40 passed`；Agent/Dialogue 相关测试 `35 passed`；`ruff check app tests`、`compileall`、`git diff --check` 和 OpenSpec 严格校验均通过。本 Change 未执行外部 MCP、真实 Provider 或浏览器人工验收，这些属于后续协议和联调 Change。
