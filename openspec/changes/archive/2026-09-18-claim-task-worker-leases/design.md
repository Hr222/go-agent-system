## Context

TM-01 固定了 Task、Attempt、Event 的状态机和幂等契约，TM-02 已将聚合及命令回执持久化到 PostgreSQL，TM-03 提供了受信任的服务端提交能力。当前 `TaskLifecycleService` 已能处理领取、续租和终态写回，但没有任务轮询器、lease 签发器或执行器注册绑定；直接先查再保存也不能证明多个进程只会有一个领取者。

本 Change 只增加平台级的受信任 Worker 执行边界。Worker 不属于 HTTP、MCP、Function Calling 或前端接口，不拥有业务任务输入解析，也不负责租约过期恢复、取消调度或重试策略扩展。

## Goals / Non-Goals

**Goals:**

- 让 Worker 能从 PostgreSQL 原子选择一个到期可执行的 `queued` Task，并在同一生命周期事实中创建 Attempt、迁移为 `running`、写入唯一 `TASK_CLAIMED` 事件。
- 在受信任执行器边界内签发不可预测的 lease，支持带递增序号的续租，并由既有生命周期 Application 校验 Attempt、token 和到期时间。
- 通过固定的 task type 到执行器绑定执行任务；成功和失败分别委托既有 `complete`/`fail` 命令，保持状态机、结果指纹和安全失败分类的幂等语义。
- 用内存替身和隔离 PostgreSQL 并发测试证明竞争领取、续租、结果回放、执行器异常和敏感数据不泄漏。

**Non-Goals:**

- 不实现 lease 过期扫描、恢复事件、自动/手动重试调度或协作式取消；这些属于 TM-05。
- 不增加任务创建、查询、事件、取消或重试的公开 HTTP/MCP/Function Calling 接口。
- 不接入 Tender、前端、E2E、Workflow 或真实业务输入存储；执行器只消费本 Change 定义的受信任执行上下文和合成测试结果。
- 不改变 Task 状态集合、提交档案、数据库表的既有关系约束；若实现需要新增内部字段，必须通过兼容迁移并保持旧聚合可读。

## Decisions

### Worker 与生命周期 Application 分工

新增 Worker Application/Runner 作为平台能力，负责轮询、生成 `worker_id`/`claim_id`、调用 lease issuer、选择执行器和隔离单次执行异常。领取、续租、成功、失败和取消确认仍统一调用 `TaskLifecycleService` 的执行器契约；Worker 不直接修改 Domain、Repository 或 ORM。这样可避免在 Worker 中复制状态转换和幂等算法。

候选选择通过 `TaskRepositoryPort` 增加原子领取语义：PostgreSQL 在一个事务中按 `queued`、`executable_at <= now` 顺序选择并锁定一行，使用 `FOR UPDATE SKIP LOCKED` 跳过其他 Worker 已锁定的任务；领域领取、Attempt/Event 写入和提交在同一事务内完成。内存替身使用等价的互斥临界区。没有候选任务时返回空结果，不产生任何事实。

### Lease 签发与验证

lease issuer 只在受信任 Worker 内生成不可预测 token 和未来到期时间，并把 token 传入执行器契约；token 不进入 `TaskView`、Event 元数据、日志或错误文本。续租必须携带当前 Attempt、token 和严格递增的 `renewal_sequence`，由 Domain 校验新到期时间晚于旧值。完成、失败和取消确认继续使用现有 lease 校验，过期、token 不匹配或 Attempt 非 active 时拒绝并保持聚合不变。

本 Change 不通过哈希替换现有领域 token 字段，也不改变 TM-02 已有的 Attempt 映射；安全边界由导入范围、结果投影和日志测试守住。后续若需要轮换或恢复 token，再单独设计迁移。

### 执行器注册与运行上下文

Composition Root 提供固定的 `task_type -> executor` 映射和 Worker 构造函数。执行器接口只接收稳定的受信任执行上下文（Task 标识、task type、安全展示元数据和当前 lease）并返回结果指纹、摘要或受控失败分类；它不能访问 Repository、Session、HTTP 请求或 Provider SDK。未知 task type、未注册执行器和执行器拒绝统一转换为不含原始异常的安全失败结果，再交给生命周期 Application 按既有重试策略处理。

一次 `poll_once` 只处理一个成功领取的 Task；执行器异常被捕获后提交受控失败，提交失败只记录安全分类并结束本轮，不影响后续轮询。Worker 不在进程内缓存 Task 状态，结果重放依赖 PostgreSQL 聚合和稳定指纹。相同成功/失败结果重放返回原状态，冲突指纹或旧 lease 返回稳定错误。

### 可观测性与安全

日志和指标只允许记录 worker_id、task_id、attempt_id、task_type、状态和安全错误代码；不得记录 token、输入指纹、原始输入或完整异常。Worker 的 idle、claim、renew、complete、fail 和 executor-rejected 结果使用结构化安全字段，便于后续 TM-05 的恢复扫描复用，但不提前改变恢复语义。

### 持久化与兼容

优先复用 `task_attempt` 已有的 lease、claim 和 renewal 字段以及 TaskRepository 的事务边界；只有 PostgreSQL 原子候选领取缺少的索引或字段才增加向后兼容迁移。迁移必须可重复执行，旧的 queued Task 在迁移后仍可被领取。回滚时停止组装 Worker，不删除已经产生的 Task/Attempt/Event；现有生命周期读取和安全投影继续可用。

## Risks / Trade-offs

- [长时间执行期间 Worker 未及时续租] → Runner 使用可配置的续租间隔并在执行器仍运行时递增 renewal sequence；续租失败立即停止结果写回，恢复留给 TM-05。
- [两个 Worker 看到同一 queued Task] → 候选选择和聚合写回共用数据库事务与行锁，集成测试使用独立 Session 验证最多一个 `TASK_CLAIMED`。
- [执行器异常泄漏敏感数据] → 只把固定错误代码和脱敏摘要交给 `fail`，日志测试断言不包含 token、输入和异常文本。
- [执行器绑定与业务策略漂移] → 当前只允许 Composition Root 的显式固定绑定；Tender 等真实业务接入在 TM-07 单独定义档案和输入来源。
- [Worker 进程崩溃留下 running Task] → 本 Change 不伪装解决恢复；保留 lease 到期事实并在看板中明确依赖 TM-05。

## Migration Plan

1. 先扩展 Task Worker/Executor Port 和 Application 契约，再实现 PostgreSQL 原子候选领取与必要索引迁移。
2. 以合成执行器接入 Composition，补充内存、PostgreSQL 并发、lease 和安全边界测试。
3. 更新架构基线、主规格和系统看板，执行全量验证并归档 Change。
4. 回滚时移除 Worker 的 Composition 绑定或关闭轮询；不删除已持久化任务事实，不回滚已有 TM-01～TM-03 数据结构。

## Open Questions

无。租约过期后的恢复策略、取消协作和重试调度由 TM-05 继续定义；真实业务执行器和输入快照由 TM-07 定义。
