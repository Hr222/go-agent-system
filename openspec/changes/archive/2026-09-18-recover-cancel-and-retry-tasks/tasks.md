## 1. 调度 Port 与候选扫描

- [x] 1.1（对应 `task-recovery-and-retry`：过期恢复）定义恢复、退避、取消和手动重试的内部 Application/Port 契约；不依赖 ORM、HTTP 或具体 Worker。
- [x] 1.2（对应场景：并发恢复）扩展 PostgreSQL Repository，以 `SKIP LOCKED` 原子扫描过期 active Attempt 和到期 `retry_wait` Task；必要索引可重复迁移且保留既有读取兼容性。
- [x] 1.3（对应场景：命令回执）为恢复、重入队和手动重试生成稳定 command_id，并复用现有生命周期事务和回执表。

## 2. 恢复、重试与取消实现

- [x] 2.1（对应 `task-recovery-and-retry`：过期 lease）实现 RecoveryCoordinator，按取消状态、剩余尝试和退避策略调用既有 `recover`，不直接修改 Domain/ORM。
- [x] 2.2（对应 `task-recovery-and-retry`：退避重入队）实现 RetryScheduler，只处理到期 `retry_wait`，调用既有 `requeue_due` 并保持事件/尝试顺序。
- [x] 2.3（对应 `task-recovery-and-retry`：协作取消）实现 CancellationCoordinator 和只读取消检查 Port；运行中只请求取消，执行器确认后调用 `confirm_cancellation`，不强杀线程或 Provider。
- [x] 2.4（对应 `task-recovery-and-retry`：手动重试）实现受信任手动重试 Application，复用 `allow_manual_retry`、`max_attempts` 和命令回执策略。
- [x] 2.5（对应安全要求）隔离单候选异常，统一安全错误码，禁止 token、输入指纹、原始异常进入日志、Event 或返回投影。

## 3. 测试与架构边界

- [x] 3.1 为内存替身补充过期恢复、取消请求/确认、退避到期、手动重试、命令重放和敏感数据脱敏测试。
- [x] 3.2 为 PostgreSQL 增加独立 Session 并发恢复/重入队测试、锁跳过、唯一 Event/回执和事务回滚测试。
- [x] 3.3 增加架构边界测试，证明调度器只能调用 Application/Port，不直接访问 ORM、Session、Repository 或公开协议层。
- [x] 3.4 执行相关 pytest、全量 `python -m pytest -q`、`ruff check app tests`、`python -m compileall -q app tests`、`git diff --check` 和 `openspec validate recover-cancel-and-retry-tasks --strict`。

## 4. 架构事实与交付

- [x] 4.1 更新 `ARCHITECTURE.md`、系统看板和主规格，明确恢复/取消/重试已实现，HTTP、Tender、前端和 E2E 仍待后续 Change。
- [x] 4.2 完成合成调度器人工验收，勾选全部任务，归档 Change，创建单独 Git commit 并推送远程。
