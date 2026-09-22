## 1. Schema health

- [x] 1.1 增加 Task 核心表集合、迁移指引和安全检查函数；用 mock Engine 验证四张表完整、缺表和 SQLAlchemy 异常分支（对应 task-runtime-readiness / schema 前置条件）。
- [x] 1.2 增加 Task schema 状态模型，并在 Composition Root 暴露只读检查；验证数据库不可用时不执行建表或写入操作。

## 2. Startup diagnostics

- [x] 2.1 在 FastAPI lifespan 中记录 Task schema ready、missing、unavailable 三种状态，并用启动测试断言对应日志分支。
- [x] 2.2 保持启动不自动迁移，补充缺表日志的可操作指引；回归验证现有 Task HTTP 路由的路径、认证拒绝和响应模型不变。

## 3. Verification

- [x] 3.1 为 schema health 完整、缺表和异常分支增加单元测试，并确认测试不依赖真实 PostgreSQL。
- [x] 3.2 为启动诊断增加回归测试，运行相关 pytest，并运行任务路由回归测试。
- [x] 3.3 执行 `openspec validate harden-task-runtime-readiness --type change --strict`，确认 Change 文档可归档。
