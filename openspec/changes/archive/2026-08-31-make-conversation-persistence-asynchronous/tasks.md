## 1. 持久化异步边界与契约

- [x] 1.1 对照 `streaming-chat-multiturn-context`、`streaming-conversation-persistence`、`conversation-message-write` 和 `conversation-turn-serialization` 的正式规格，整理普通流式 Chat 的持久化操作矩阵；完成条件：明确创建/解析、user 写入、上下文读取、assistant 写入的边界，并书面确认不改变主体、sequence、租约、预算和失败语义。（对应 Requirements：持久化操作不得阻塞异步事件循环、Session 生命周期）
- [x] 1.2 在 Dialogue Application/Ports 定义异步 Conversation 持久化 Port、同步 Worker Port 和 Worker Factory Port；完成条件：接口只依赖 Conversation 领域对象与安全主体，不导入 SQLAlchemy、Session、Composition 或具体 Repository。（对应 Requirement：持久化操作不得阻塞异步事件循环）

## 2. 同步 Worker 与 Session 生命周期

- [x] 2.1 实现每次短操作独立创建 Worker/Session 的 Composition 适配器；完成条件：创建/解析会话、消息追加和最近消息读取均通过现有 Application Service/Repository 执行，每次操作成功提交、异常回滚并关闭 Session。（对应 Requirement：每个短操作独立收口）
- [x] 2.2 实现异步持久化门面及取消收口逻辑；完成条件：同步操作通过 `asyncio.to_thread` 或等价边界运行，调用方取消不会遗留后台 Worker，Worker 完成关闭后才重新抛出取消异常。（对应 Requirement：异步取消不得遗留持久化 Worker）
- [x] 2.3 保持现有 Conversation 错误和安全边界；完成条件：越权/不存在会话仍按既有拒绝类别处理，数据库异常仍转换为既有流式持久化失败，不接受客户端提供的 owner 或权限替代值。（对应父规格：主体访问与失败语义）

## 3. Streaming Dialogue 接入

- [x] 3.1 将普通流式 Runtime 的创建/解析、user 写入、最近上下文读取和 assistant 写入切换为异步持久化 Port；完成条件：同步 Conversation 方法不直接在异步 Runtime 中调用，Provider 流开始前后仍保持既有轮次时序。（对应 Requirements：持久化操作不得阻塞异步事件循环、Session 生命周期）
- [x] 3.2 对齐现有 Conversation 轮次租约和 sequence 截止；完成条件：租约仍覆盖 user 写入至 assistant 终态，当前 user sequence 仍是上下文读取边界，同会话请求不交错，不新增第二套锁或队列。（对应父规格：轮次串行和上下文窗口）
- [x] 3.3 保持普通流式成功、取消、上游失败、空回答、预算失败和 assistant 写入失败语义；完成条件：user 先持久化，只有完整非空 assistant 才写入，任何失败不保存部分 assistant，底层 Provider 流在所有退出路径关闭。（对应父规格：普通流式多轮对话和失败语义）
- [x] 3.4 调整 Composition/HTTP 容器生命周期，确保请求级 Session 不传入 Streaming Conversation Runtime，也不被 Provider 流继续使用；完成条件：Runtime 只接收异步持久化 Port，依赖组装测试能证明测试替身可注入且流式路径不共享请求 Session。（对应 Requirement：不跨模型生成持有 Conversation Session）

## 4. 行为、资源与数据库验证

- [x] 4.1 增加阻塞 Worker 的事件循环回归测试；完成条件：模拟同步数据库等待时心跳、跨会话任务或其他异步任务仍能运行，且 Worker 返回后原操作结果正确。（对应 Requirement：持久化操作不得阻塞异步事件循环）
- [x] 4.2 增加 Session 创建/提交/回滚/关闭和请求取消测试；完成条件：每个短操作只使用自己的 Session，成功、异常、取消和流提前关闭均不遗留 Worker、Session 或轮次租约。（对应 Requirements：Session 生命周期、异步取消）
- [x] 4.3 增加 PostgreSQL 流式交界集成测试；完成条件：真实数据库验证消息顺序、user/assistant 持久化、上下文读取和连接释放；数据库不可用时明确记录未运行原因，不把替身测试当作集成验收。（对应 Requirement：不跨模型生成持有 Conversation Session）
- [x] 4.4 增加 Composition、架构边界和 Interaction 回归测试；完成条件：Dialogue/Ports 不依赖 ORM 或 Container，普通 Chat 仍只经过 Streaming Conversation Runtime，HTTP/SSE 字段和 Agent 分支不发生非本 Change 变更。（对应父规格：模块边界和统一入口）

## 5. 完成校验与规格收口

- [x] 5.1 运行受影响的 Conversation、Dialogue、Interaction、Application 和架构测试；完成条件：稳定替身测试全部通过，并记录 PostgreSQL 集成测试的实际结果。
- [x] 5.2 运行 `ruff check app tests`、`python -m compileall -q app tests` 和 `git diff --check`；完成条件：所有命令成功，未完成项明确记录原因。
- [x] 5.3 运行 `openspec validate "make-conversation-persistence-asynchronous" --strict --no-interactive`，并在实现与验证完成后同步 `streaming-chat-multiturn-context` 正式规格；完成条件：delta spec、实现、测试和任务清单一致，随后再执行归档。
