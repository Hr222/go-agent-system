## 1. 执行器与 Worker 契约

- [x] 1.1（对应 `task-worker-execution`：受信任边界）定义 Worker、LeaseIssuer、ExecutorRegistry 和执行上下文 Port；Domain/Application 不得导入 SQLAlchemy、HTTP、Provider SDK 或具体执行器类型。
- [x] 1.2（对应 `task-lifecycle-management`：领取与续租）收紧领取、续租和结果回写的 Application 契约，确保 lease 只在执行器内部返回，安全 `TaskView` 不包含 Attempt 或 token。
- [x] 1.3（对应 `task-worker-execution`：固定绑定）在 Composition Root 增加显式 task type 到执行器的固定绑定，未知 task type 返回可断言的安全错误且不把 token 或原始输入写入日志。

## 2. PostgreSQL 原子领取

- [x] 2.1（对应 `task-worker-execution`：原子领取）扩展 `TaskRepositoryPort` 和 PostgreSQL Repository，在同一事务中按 `queued`/可执行时间选择并锁定任务，使用跳过已锁定行的并发策略；无候选时返回空结果。
- [x] 2.2（对应 `task-lifecycle-management`：唯一 active Attempt）让候选领取、Attempt 创建、`running` 状态和唯一 `TASK_CLAIMED` Event 共用现有聚合保存事务；必要索引或约束通过可重复执行迁移增加，并保持旧任务可读。
- [x] 2.3（对应场景：并发 Worker 竞争）用独立 PostgreSQL Session 验证两个 Worker 竞争同一 Task 时最多一个 active Attempt、一条领取 Event，另一方得到空/重放/稳定状态错误且无部分写入。

## 3. Worker 执行与 lease

- [x] 3.1（对应 `task-worker-execution`：领取与 lease）实现单次轮询：生成 worker/claim 标识和不可预测 lease，领取一个 Task，构造内部执行上下文；没有任务时不产生生命周期事实。
- [x] 3.2（对应 `task-worker-execution`：续租）实现执行期间的受控续租，严格递增 renewal sequence；续租失败、过期或 token 不匹配时停止结果写回并释放本轮资源。
- [x] 3.3（对应 `task-worker-execution`：结果回写）将执行器成功委托既有 `complete`，失败/拒绝委托既有 `fail`，复用结果指纹、重试策略和安全失败代码；同结果重放不重复 Event，冲突结果稳定拒绝。
- [x] 3.4（对应 `task-worker-execution`：异常隔离）捕获执行器和持久化异常，转换为固定安全错误分类；日志和持久化数据不得包含 lease token、输入指纹、原始异常或 Provider 响应，且单次失败不得污染下一次轮询。

## 4. 测试与架构边界

- [x] 4.1 为内存替身补充 Worker/Application 测试：无任务、成功、执行器拒绝、续租、过期 lease、旧 token、重复领取和结果幂等场景均有可观察断言。
- [x] 4.2 为 PostgreSQL 适配器补充迁移、并发领取、Attempt/Event 唯一性、事务回滚和重启后 lease/结果回放测试；测试不依赖真实外部 Provider。
- [x] 4.3 增加架构边界测试，证明 Worker/Executor 只能调用 Application/Port，生产代码不暴露含 lease 的通用协议，不直接导入 ORM、Session 或 Repository。
- [x] 4.4 执行相关 pytest、全量 `python -m pytest -q`、`ruff check app tests`、`python -m compileall -q app tests`、`git diff --check` 和 `openspec validate claim-task-worker-leases --strict`；未通过不得勾选任务。

## 5. 架构事实与交付

- [x] 5.1 根据实际实现更新 `ARCHITECTURE.md`、`docs/go agent system - 系统看板.md` 和主规格，明确 Worker 已实现范围以及恢复、取消、重试、HTTP、Tender、前端和 E2E 仍未实现。
- [x] 5.2 人工验收 Worker 只通过 Composition 固定绑定运行、任务安全投影不泄漏 lease、执行器异常可继续下一轮；记录验收证据后勾选全部任务并归档 Change。
