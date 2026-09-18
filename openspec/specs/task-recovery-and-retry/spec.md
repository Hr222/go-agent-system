# task-recovery-and-retry Specification

## Purpose

定义受信任内部调度器对过期 lease、退避重试、协作式取消和手动重试的安全、幂等、持久化与依赖边界。

## Requirements

### Requirement: 过期 lease 由独立调度器原子恢复

系统 MUST 由 RecoveryCoordinator 扫描 `running` 或 `cancel_requested` 且 active Attempt 已过期的候选，并通过既有生命周期 Application 在同一持久化事务内结束 Attempt、记录唯一恢复 Event 和命令回执。多个恢复器 MUST 使用 PostgreSQL `SKIP LOCKED` 避免重复处理；取消中的任务转为 `cancelled`，未耗尽任务按策略进入 `queued` 或 `retry_wait`，耗尽任务进入 `failed` 并使用安全 `LEASE_EXPIRED` 代码。

#### Scenario: 并发恢复过期尝试

- **WHEN** 两个恢复器同时扫描同一过期 active Attempt
- **THEN** 最多一个恢复器完成状态转换并写入恢复 Event
- **AND** 另一个恢复器得到空结果或当前稳定状态

### Requirement: 退避任务只能在到期后重新入队

系统 MUST 由 RetryScheduler 只扫描 `retry_wait` 且 `available_at <= now` 的任务，并调用 `requeue_due` 保留尝试历史和事件顺序。重入队命令 ID MUST 稳定且可重放，不得重复追加 Event；未到期任务必须保持原状态。

#### Scenario: 退避到期重新入队

- **WHEN** `retry_wait` Task 到达 `available_at`
- **THEN** 调度器将其转为 `queued` 并只追加一条重入队 Event
- **AND** 退避未到期的 Task 保持原状态

### Requirement: 取消必须协作完成

系统 MUST 对排队任务直接取消，对运行中任务只写入 `cancel_requested`；执行器只能在持有有效 lease 的安全检查点观察取消信号，并通过 `confirm_cancellation` 完成终态。调度器不得强杀线程或外部 Provider。

#### Scenario: 运行中任务协作取消

- **WHEN** 取消协调器请求取消一个 `running` Task
- **THEN** Task 进入 `cancel_requested` 且 active Attempt 保持不变
- **AND** 执行器确认后 Task 才进入 `cancelled`

### Requirement: 手动重试受服务端策略约束

系统 MUST 只允许受信任内部 Application 对 `allow_manual_retry` 且未耗尽尝试次数的 `failed` Task 发起手动重试。相同 command_id 重放 MUST 返回当前结果，不重复追加重试 Event；错误只返回固定安全分类码，不泄漏 token、输入或底层异常。

#### Scenario: 手动重试策略拒绝

- **WHEN** 手动重试命令针对不允许重试或已耗尽尝试的 `failed` Task
- **THEN** 命令返回固定安全错误码并保持状态和事件不变
- **AND** 返回内容不包含 lease token、输入指纹或底层异常

### Requirement: 调度候选失败必须隔离

批量调度中的单个候选失败 MUST 回滚该候选事务并返回固定错误码，继续处理其他候选。扫描候选、协调器和 Composition Root 不得依赖 HTTP、ORM 或具体数据库 Session。

#### Scenario: 单候选失败隔离

- **WHEN** 批量调度中的一个候选在生命周期写入时失败
- **THEN** 该候选的状态、Event 和命令回执全部回滚并返回固定错误码
- **AND** 调度器继续处理后续候选
