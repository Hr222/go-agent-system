## 1. 领域审计契约

- [x] 1.1 实现领取即开始的中文领域说明，并收紧 `TaskEvent` 元数据白名单、标准 JSON 有限标量、失败码和结果指纹校验；未知或敏感数据必须被拒绝。
- [x] 1.2 补充领取单事件、非有限 JSON、未知/敏感字段和不安全代码/指纹的领域测试；现有状态转换与幂等测试必须继续通过。

## 2. Application 与测试边界

- [x] 2.1 将 lease 命令与结果移入不公开再导出的执行器契约模块，保持 `TaskView` 为无内部执行事实的安全投影。
- [x] 2.2 将 `InMemoryTaskRepository` 移至 `tests/task/` 测试范围，并更新导入；运行时代码不得再定义该测试替身。
- [x] 2.3 扩充架构边界测试，验证生产 Task 模块不包含内存测试仓储，通用 Application 包不再公开含 lease 的执行器类型。

## 3. 架构事实与验证

- [x] 3.1 更新 `ARCHITECTURE.md` 与系统看板，说明领取即开始、测试替身位置和受信任执行器 lease 边界，不把 TM-02 行为写成已实现。
- [x] 3.2 执行相关和全量 `pytest`、`ruff check app tests`、`python -m compileall -q app tests`、`openspec validate harden-task-lifecycle-contracts --strict`、`openspec validate --all --strict` 以及 Git 差异检查；验证成功后更新任务状态。
