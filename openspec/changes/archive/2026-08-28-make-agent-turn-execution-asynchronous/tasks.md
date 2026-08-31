## 1. Dialogue Agent turn 异步边界

- [x] 1.1 在 Dialogue Application 定义 Conversation turn 异步执行入口、确认操作契约、已批准 Agent 调用和受控结果；完成条件：入口先取得共享租约，再调用由 Interaction 提供的确认操作，Interaction 不直接获取或释放租约。
- [x] 1.2 实现租约拥有的 supervisor 与 worker 执行模型；完成条件：同步 Agent/continuation 在 worker 中运行，不同 Conversation 的请求能在其间推进，等待锁取消不创建 worker，已启动 worker 的请求取消不提前释放租约且 task 异常被回收。
- [x] 1.3 定义 `DialogueAgentTurnWorkerPort` 并由 Composition 绑定每轮私有 worker factory；完成条件：Dialogue Application 不导入 `SessionLocal`、`Session`、Repository 或 `ApplicationContainer`，worker 不接收请求级持久化对象且每轮完成后关闭私有资源。

## 2. 确认编排与状态收口

- [x] 2.1 将 Interaction Chat Application 与 HTTP 确认入口改为委托 Dialogue Conversation turn 入口；完成条件：Interaction 保留 Gateway proposal 消费、目录/权限/输入复核和 `GatewayResult` 映射，确认 API 与 `cancel` 动作外形不变，Interaction 不编排租约生命周期。
- [x] 2.2 在锁内统一 proposal 与 pending invocation 的终态收口；完成条件：等待锁取消不消费状态，proposal 已消费后的校验拒绝、pending 缺失、Agent/continuation 成功或失败均不遗留 matching pending invocation，重复确认不重复执行 Agent。
- [x] 2.3 保持会话事实、错误与授权边界；完成条件：同会话 Agent 的 event/assistant 终态先于后续 Chat，上游/持久化/预算失败仍遵循既有受控响应和 assistant 写入语义，worker 仅接收 Gateway 已批准的分发信息且确认复核失败时不启动 Agent。

## 3. 时序、资源与架构验证

- [x] 3.1 增加受控阻塞 worker 的同 Conversation 集成测试；完成条件：Agent 执行中普通 Chat 不写 user、不读历史、不调用 LLM，释放 worker 后 Chat 读取 Agent result 与 continuation assistant 的终态。
- [x] 3.2 增加跨 Conversation、取消与状态收口测试；完成条件：长 Agent worker 期间另一 Conversation 能到达模型/Agent 起点，等待取消可重试，已启动后取消保持租约，proposal 消费后拒绝清理 pending。
- [x] 3.3 增加 Composition 与架构边界测试；完成条件：共享协调器和 worker Port 只经 Composition 组装，Dialogue Application 不依赖 ORM/container，Interaction 保留确认控制面但不直接管理 `ConversationTurnLease`，HTTP/Interaction 不依赖 SQLAlchemy Session。

## 4. 完成检查

- [x] 4.1 运行受影响的 Dialogue、Interaction、Composition、架构与 HTTP 测试，以及 `ruff check app tests`、`python -m compileall -q app tests`；完成条件：所有可运行命令通过，外部 Provider 使用稳定替身。
- [x] 4.2 运行 `openspec validate "make-agent-turn-execution-asynchronous" --strict --no-interactive`、`git diff --check` 并记录未运行项；完成条件：严格规格校验和差异检查通过，所有任务仅在对应证据存在后勾选。
