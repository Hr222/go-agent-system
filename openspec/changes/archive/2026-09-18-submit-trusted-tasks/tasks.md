## 1. 受信任提交 Application 契约

- [x] 1.1 新增不可变的提交档案和不含 owner/task type/策略字段的提交命令，校验档案固定策略与展示字段白名单。（`trusted-task-submission`）
- [x] 1.2 实现受信任提交服务：从已认证 `RequestPrincipal` 导出 owner，校验展示元数据并委托既有生命周期提交，保留 TM-02 创建幂等语义。（`trusted-task-submission`、`task-lifecycle-management`）
- [x] 1.3 增加受控主体错误和策略错误；拒绝路径不得创建任何 Task 生命周期事实。（`trusted-task-submission`）

## 2. 组装与边界

- [x] 2.1 在 Composition 增加受信任提交服务构造函数，仅通过显式提交档案与现有 PostgreSQL Repository 组装，不新增 HTTP 或运行时注册表。（`trusted-task-submission`）
- [x] 2.2 增加架构边界测试：业务层不得导入低层创建命令或生命周期服务；Task 路由、公开 Schema 与 Agent 协议不得新增任务创建入口。（`trusted-task-submission`、`current-architecture-baseline`）

## 3. 验证与架构事实

- [x] 3.1 使用测试替身覆盖已认证主体提交、主体拒绝、固定策略、展示字段拒绝和同键重放；验证没有重复 Task/Event。（`trusted-task-submission`）
- [x] 3.2 使用隔离 PostgreSQL schema 覆盖受信任提交重启后的幂等重放和拒绝路径零持久化。（`trusted-task-submission`）
- [x] 3.3 更新 `ARCHITECTURE.md`、系统看板和主规格，准确记录受信任内部提交已实现，并保留 HTTP、Worker、业务接入、前端、E2E 与 Workflow 的未实施边界。（`current-architecture-baseline`）
- [x] 3.4 执行相关与全量 `pytest`、`ruff check app tests`、`python -m compileall -q app tests`、`openspec validate submit-trusted-tasks --strict`、`openspec validate --all --strict` 和 `git diff --check`；全部通过后才勾选任务与归档 Change。
