## Context

TM-01 的 `Task.claim()` 已原子地把 Task 从 `queued` 迁移到 `running`，并创建 Attempt 和 `TASK_CLAIMED` 事件。原规格把领取与开始并列，容易让后续 Worker Change 误以为需要补写第二个开始事件。事件元数据目前只作宽松的 Python 标量检查，内存仓储也错误地随 Application 运行时代码发布；此外，lease 类型虽有文字说明，但与普通 Application 契约同处一层。

本 Change 不改变状态集合、持久化模型或并发语义。它只在 TM-02 固化 PostgreSQL 事件表之前，把现有领域与执行器边界收紧。

## Goals / Non-Goals

**Goals:**

- 固定“领取即开始”的单一状态转换和审计事实。
- 让所有写入的事件元数据都是安全、有限且可标准 JSON 序列化的数据。
- 使运行时代码只包含 Port 和 Application 能力，测试替身只位于测试范围。
- 让安全 Task 投影与受信任执行器 lease 契约在导入边界上可区分。

**Non-Goals:**

- 不新增独立的开始命令、Worker、HTTP 路由、数据库模型、迁移或事务。
- 不实现外部执行器注册、lease 生成器、跨进程原子领取或真实审计查询。
- 不修改 Task 状态、失败重试、取消或持久化的既有业务语义。

## Decisions

### 领取即开始，不追加第二条开始事件

一次合法领取创建 active Attempt、迁移到 `running`，并写入唯一 `TASK_CLAIMED` 事件；该事件同时是执行开始的审计事实。规格不再把“开始”描述为独立生命周期动作。

替代方案是在 TM-01 新增 `TASK_STARTED`。这会引入没有实际执行器边界支撑的第二转换和重复审计记录，也会让 TM-04 重新定义何时开始，因此不采用。

### 事件按类型白名单化，并通过标准 JSON 校验

Domain 为每种 `TaskEventType` 定义允许的元数据键；生成事件只能使用对应字段。元数据值只接受有限 JSON 标量，先拒绝敏感键、未知键与非有限浮点数，再用 `json.dumps(..., allow_nan=False)` 验证。失败码和结果指纹使用受限的安全标识格式，避免把完整异常或 Provider 原始响应伪装成审计字段。

键名黑名单仍保留为纵深防御，但不再作为唯一安全保证。替代方案是只在 TM-02 的 JSONB 适配器校验；这会让领域事件在内存阶段和持久化阶段行为不一致，因此不采用。

### 测试替身与执行器 lease 分离

`InMemoryTaskRepository` 是测试替身，移动到 `tests/task/`，生产 `app/platform/task` 只保留 Domain、Application、Ports 和错误定义。其结构化满足 `TaskRepositoryPort`，但不作为运行时适配器或并发实现。

`TaskView` 是可安全投影；含 token 的命令、`AttemptLease` 和领取/续租结果移入不由 `application` 包公开导出的执行器契约模块。`TaskLifecycleService` 仍可返回该内部结果给未来受信任 Worker；HTTP 或其他协议适配器不得把它投影给外部调用者。

替代方案是保留所有类型在公共 `contracts.py`，仅依赖注释。这不足以防止未来接口层误导入含 token 的结果，因此不采用。当前没有 HTTP 适配器或 Composition Root 绑定需要迁移。

## Risks / Trade-offs

- [字段白名单遗漏未来事件所需数据] → 新事件类型必须在领域规则、规格和测试中同时显式增加字段。
- [安全代码格式拒绝现有调用方值] → 当前 TM-01 没有运行时调用方；测试覆盖已有 `UPPER_SNAKE_CASE` 和现有指纹格式。
- [移动测试替身改变测试导入] → 只更新测试导入，并以架构测试禁止运行时代码定义该类。
- [内部执行器模块仍可被 Python 显式导入] → 通过不公开再导出、明确中文文档和架构测试建立项目约束；真正协议隔离留给 TM-04/TM-06。

## Migration Plan

1. 收紧领域事件校验与安全标识校验，补充正反测试。
2. 移动内存测试替身、拆分执行器契约，并更新架构断言和文档。
3. 完成后运行全量验证、同步主规格并归档本 Change；失败时可回退本 Change 的单一提交，不涉及数据迁移。

## Open Questions

无。TM-02 仍只负责持久化生命周期，不引入 Worker 或外部协议。
