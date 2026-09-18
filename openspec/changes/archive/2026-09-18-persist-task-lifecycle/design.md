## Context

TM-01 已固定 Task、Attempt、Event、命令幂等和安全审计的领域契约，但现有 Repository 仅是 `tests/task/` 的内存替身。项目已有同步 SQLAlchemy Session、`app/infrastructure/persistence` ORM/Repository、`sql/` 顺序 SQL 迁移和 `SchemaHarness` 隔离 PostgreSQL schema 测试模式。TM-02 要把领域聚合映射到这些既有机制，而不把 ORM 或事务细节带入 Domain/Application。

## Goals / Non-Goals

**Goals:**

- 让 Task、Attempt、Event 和命令回执可跨进程重启恢复为同一领域聚合。
- 将创建幂等、领取幂等、事件顺序和单 active Attempt 的关键不变量落实为数据库约束与事务语义。
- 让一次状态变更、对应事件和命令回执在同一数据库事务内成功或回滚。
- 用真实 PostgreSQL 隔离 schema 验证迁移、映射、重放和并发冲突。

**Non-Goals:**

- 不实现任务提交 HTTP、owner 查询、Worker 轮询、lease 签发/续租调度、恢复扫描或外部执行器。
- 不实现 Tender 接入、前端、E2E、Workflow 或跨任务依赖。
- 不修改 TM-01 状态集合、状态转换、事件安全字段或 TaskView 的安全投影。
- 不新增数据库配置、迁移框架或异步 ORM；复用现有 PostgreSQL 配置、Session 与 SQL 脚本约定。

## Decisions

### 聚合表、子事实表与命令回执表

新增 `task`、`task_attempt`、`task_event` 和 `task_command_receipt` 四张表。`task` 保存当前聚合状态和提交幂等键；Attempt 与 Event 通过外键从属 Task，按领域序号持久化；回执表记录成功处理过的取消、重排队、手动重试和恢复命令，供重启后的重放判断。

数据库约束至少包括：

- `(owner_subject, task_type, idempotency_key)` 唯一，防止重复创建。
- `(task_id, number)`、`(task_id, worker_id, claim_id)`、`(task_id, sequence)` 和 `(task_id, transition_id)` 唯一，分别固定 Attempt、领取和 Event 幂等事实。
- active Attempt 的部分唯一索引、Task/Attempt/Event 状态和值的检查约束、外键级联与 JSONB 对象检查。

领域层仍负责合法转换和安全元数据规则；数据库负责跨进程的完整性下限。替代方案是只依赖 Application 先查再写，这在两个进程同时领取或提交时无法保证正确性，因此不采用。

### Repository 持有事务边界，Application 只使用 Port

`TaskRepositoryPort` 演化为三类语义：原子创建或读取同一提交、读取并锁定可变聚合、在一次提交中写回聚合及可选命令回执。`TaskLifecycleService` 对会改变状态的命令先经 Port 锁定 Task，再读取回执、执行既有 Domain 转换并保存；Repository 使用父 Task 行锁串行同一聚合的写入。

提交重复时 PostgreSQL 唯一约束是最终仲裁。Repository 在插入冲突后回滚局部事务、读取既有 Task 并由 Application 比对输入指纹，返回原结果或稳定冲突。替代方案是 Port 暴露 SQLAlchemy `Session` 或让每个 `save`/回执各自提交；前者破坏分层，后者会产生“状态已提交但回执未写入”的重放漏洞，因此不采用。

### 显式 ORM 映射与 SQL 迁移双轨验证

在 `app/infrastructure/persistence/models/` 定义 ORM records，在独立 mapper 中双向转换 Task 聚合，Repository 是唯一使用 ORM/Session 的 Task 适配器。`sql/013_task_lifecycle.sql` 创建同等的幂等 PostgreSQL 结构；因没有历史 Task 数据，不做回填。模型会在 `models/__init__.py` 注册，使 `SchemaHarness` 的 `Base.metadata.create_all()` 覆盖集成测试；迁移测试另行验证脚本可重复执行。

Composition 只提供 PostgreSQL Task Repository 的构造函数，不提前在运行时 Root 中创建 Worker 或 HTTP 对象图。替代方案是直接在 Application 中创建 Repository，违反 Composition Root 边界，因此不采用。

### lease 数据保留为内部执行事实

TM-01 已要求 lease 不进入 Event 或安全 TaskView。TM-02 将它作为 Attempt 的内部持久化字段恢复，以保持现有领域 lease 比对契约；映射器、日志和错误投影不得输出它。对 lease token 进行哈希需要同时改变领域比对、签发和恢复策略，而这些属于 TM-04 的 Worker lease 设计，因此不在本 Change 提前引入。

## Risks / Trade-offs

- [ORM 表和 SQL 脚本漂移] → 用迁移幂等测试、`Base.metadata` 隔离 schema 测试和约束断言共同覆盖。
- [并发提交在唯一冲突后返回错误而不是原结果] → Repository 对提交唯一冲突执行受控回读，Application 仅按输入指纹决定重放或冲突。
- [一次保存遗漏子事实或回执] → 聚合保存和回执写入必须处在一个事务，失败测试断言没有部分行残留。
- [lease token 被错误传播到安全数据] → Event/TaskView 继续复用 TM-01 校验；Repository 测试检查 Event JSON 不含 token，禁止在日志中记录 Attempt 实体。
- [现有数据库未执行新 SQL] → Repository 在缺表时返回受控的 schema 未初始化错误和明确的 `sql/013_task_lifecycle.sql` 指引；不尝试运行时建表。

## Migration Plan

1. 增加模型、迁移脚本、映射器、Port 原子语义和 PostgreSQL Repository。
2. 在隔离 schema 运行 ORM/Repository 与迁移幂等测试；生产部署按 `sql/013_task_lifecycle.sql` 执行。
3. 更新 Composition、架构基线和看板，执行全量验证后归档 TM-02。
4. 回滚时停止使用 Task Repository；新表不被旧代码引用。若已写入任务事实，不删除表或数据，后续迁移处理兼容性。

## Open Questions

无。TM-03 负责受信任生产者，TM-04 再决定 lease token 的签发、Worker 领取与恢复调度。
