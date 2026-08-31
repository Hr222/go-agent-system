## 1. Conversation 最近窗口契约

- [x] 1.1 在 `app/platform/conversation` 增加上下文专用的最近消息读取 Port 与 Application Capability，定义 `conversation_id`、`through_sequence`、消息数量上限和升序结果；完成条件：非法 UUID、非正 sequence、非法上限被拒绝，公开正向历史分页契约保持不变。
- [x] 1.2 在 PostgreSQL Conversation 适配器实现 `sequence <= through_sequence` 的倒序限量查询，并在适配器内恢复升序；完成条件：长会话只返回策略上限内的最近消息，不加载更早消息，空窗口和跨会话输入均有明确结果。
- [x] 1.3 验证最近窗口查询使用现有 `(conversation_id, sequence)` 唯一约束提供的索引；完成条件：PostgreSQL 集成测试覆盖执行计划或等价查询证据，只有索引不足时才新增最小迁移，且原有历史分页测试继续通过。
- [x] 1.4 在 Conversation Composition Root 组装最近窗口服务并补充架构边界测试；完成条件：Domain/Ports 不依赖 ORM，具体 Repository 只在 Composition/Infrastructure 出现，且不改变既有租约的组装位置。

## 2. 流式 Dialogue 的异步持久化边界

- [x] 2.1 为流式 Conversation Runtime 增加异步持久化门面或 Port，使用 session factory 在 worker 中执行同步 Conversation Access、消息写入和最近窗口读取；完成条件：每个短操作独立创建、提交/回滚并关闭 Session，请求级 Session 不跨线程共享，既有轮次租约不进入 worker 或数据库长事务。
- [x] 2.2 调整 Composition Root 和应用容器，为普通流式 Chat 注入异步持久化适配器；完成条件：模型流开始前和结束后的所有 Conversation 持久化操作均通过该边界执行，Provider 流期间不持有 Conversation Session/连接，普通 Chat 与 Agent 继续共享同一进程级轮次协调器。
- [x] 2.3 保持普通流式 Runtime 的消息与资源生命周期；完成条件：user 仍先落库，只有完整非空回答才写 assistant，取消、上游失败、预算失败和 assistant 写入失败不写部分 assistant，模型流在所有退出路径关闭。

## 3. 本轮上下文读取边界接入

- [x] 3.1 在既有轮次租约内完成 user Message 写入，保存其 sequence，并使用该 sequence 调用最近窗口读取能力；完成条件：Runtime 不再正向分页扫描完整历史，Context Builder 继续接收有序窗口、现有策略和现有预算，sequence 只作为读取边界。
- [x] 3.2 更新 LLM 请求构造，确保本轮窗口中当前 user 只作为 `user_prompt` 出现一次，读取边界之外的后续消息不进入 `history_messages`；完成条件：角色、sequence 顺序、跨会话隔离和当前输入唯一性测试通过。
- [x] 3.3 对齐既有轮次租约与 sequence 读取边界；完成条件：同一 Conversation 的请求 B 在 A 的租约释放前不写入 user、不读取上下文、不调用 Provider，A 的读取不超过自身 user sequence，A 收口后 B 能读取 A 的完整终态事实；不新增锁、FIFO 队列或长事务。

## 4. 行为、性能与回归验证

- [x] 4.1 增加 Conversation/Dialogue 单元测试；完成条件：覆盖长历史有界读取、sequence 截止、空窗口、非法参数、预算裁剪、当前 user 超预算和当前输入不重复。
- [x] 4.2 增加 PostgreSQL 持久化与 Dialogue 交界集成测试；完成条件：PostgreSQL 覆盖 sequence 截止、消息顺序事实、Session/连接释放和历史分页不回归，Dialogue 覆盖既有租约下的同会话等待与跨会话并行。
- [x] 4.3 增加异步事件循环阻塞回归测试；完成条件：模拟阻塞数据库操作时事件循环仍可处理心跳或并发任务，且流式取消后所有 worker 任务和 Provider 流均释放。
- [x] 4.4 更新应用容器、Interaction Chat Stream 和架构边界测试；完成条件：普通 Chat 仍只经过一条 Streaming Conversation Runtime，Agent invocation/continuation 分支不受影响，SSE 事件外形不变。
- [x] 4.5 运行 OpenSpec 严格校验、相关 pytest、PostgreSQL 集成测试、架构测试、全量后端测试、Ruff、`compileall` 和 `git diff --check`；完成条件：所有可运行检查有结果记录，未运行项明确说明原因，不修改看板文件。
