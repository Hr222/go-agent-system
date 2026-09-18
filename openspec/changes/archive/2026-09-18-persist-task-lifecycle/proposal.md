## Why

TM-01 的任务状态机和命令幂等目前只由内存测试替身验证，进程重启、多个进程和 PostgreSQL 约束下都不能保留任务事实。TM-02 必须先把 Task、Attempt、Event 与命令回执原子地持久化，才能安全地继续实现受信任提交和 Worker lease。

## What Changes

- 为 Task、Attempt、Event 和命令回执新增 PostgreSQL ORM 模型、映射器与顺序 SQL 迁移脚本。
- 以唯一约束、检查约束、外键、索引和事务锁实现提交幂等、Attempt/Event 序列唯一性及单 active Attempt 的持久化不变量。
- 将 `TaskRepositoryPort` 收紧为原子创建/读取锁定/保存聚合与命令回执的契约，并实现 PostgreSQL Repository；Application 不直接依赖 SQLAlchemy Session 或 ORM 类型。
- 用隔离 PostgreSQL schema 覆盖创建重放、幂等冲突、领取重放、事件序列、命令回执和并发写入场景。
- 同步架构基线和看板，准确记录 Task Management 已拥有 PostgreSQL 生命周期存储，但仍未实现 Worker、HTTP、业务接入、前端或 E2E。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `task-lifecycle-management`: 任务生命周期事实从仅内存验证替身扩展为可事务持久化的 PostgreSQL Repository。
- `current-architecture-baseline`: 记录 Task Management 已实现持久化边界及未实施的 Worker 和协议阶段。

## Impact

- 影响 `app/platform/task` 的 Port/Application 契约、`app/infrastructure/persistence` 的模型和 Repository、`app/composition` 的适配器组装，以及 `sql/` 迁移和 PostgreSQL 集成测试。
- 使用现有 PostgreSQL 配置和同步 Session；不新增环境变量、HTTP 契约、外部 Provider 或前端依赖。
- 不改变 TM-01 状态机语义，不实现 lease 调度/恢复 Worker、owner HTTP 查询、Tender 接入或 Workflow。
