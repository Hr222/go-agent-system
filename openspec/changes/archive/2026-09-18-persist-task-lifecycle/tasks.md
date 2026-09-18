## 1. 持久化模型与迁移

- [x] 1.1 为 Task、Attempt、Event 和命令回执新增 PostgreSQL ORM records、双向 mapper 与模型注册；字段、外键、状态/JSON 检查约束及安全数据边界必须映射 TM-01 聚合。
- [x] 1.2 新增可重复执行的 `sql/013_task_lifecycle.sql`，实现提交、领取、Attempt/Event 序列、转换标识和单 active Attempt 的唯一/索引约束；不进行历史数据猜测或回填。

## 2. 原子 Repository 契约

- [x] 2.1 演化 `TaskRepositoryPort` 和 `TaskLifecycleService`，使创建重放、聚合锁定读取、状态写回与命令回执具备可测试的原子语义，且 Application 不导入 SQLAlchemy 类型。
- [x] 2.2 实现 PostgreSQL Task Repository 与 Composition 构造函数：相同聚合写入使用行锁，提交唯一冲突受控回读，事务失败时回滚 Task、Attempt、Event 和回执。
- [x] 2.3 为缺少任务表的运行环境提供受控 schema 未初始化错误和 `sql/013_task_lifecycle.sql` 指引；不在运行时自动建表。

## 3. PostgreSQL 验证

- [x] 3.1 用隔离 schema 验证聚合保存/重载、重启后命令重放、安全投影和不泄漏 lease 的 Event JSON。
- [x] 3.2 验证 SQL 迁移可重复执行，以及数据库拒绝重复提交键、重复 Attempt/Event、孤立子事实和第二个 active Attempt。
- [x] 3.3 使用独立 Session 覆盖并发同一提交、竞争领取和事务失败回滚；结果必须符合 TM-01 的重放或稳定错误语义。

## 4. 架构事实与交付

- [x] 4.1 更新 `ARCHITECTURE.md`、系统看板、架构边界测试和主规格，准确记录 PostgreSQL 生命周期持久化已实现，同时保留 Worker、HTTP、业务接入、前端、E2E 和 Workflow 的未实施边界。
- [x] 4.2 执行相关与全量 `pytest`、`ruff check app tests`、`python -m compileall -q app tests`、`openspec validate persist-task-lifecycle --strict`、`openspec validate --all --strict`、迁移人工验收与 Git 差异检查；全部通过后才勾选任务和归档 Change。
