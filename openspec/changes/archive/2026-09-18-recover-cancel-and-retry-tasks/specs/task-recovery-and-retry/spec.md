# task-recovery-and-retry Specification

## Purpose

定义受信任调度器对过期 lease、退避重试、协作式取消和手动重试的安全、幂等和持久化行为。

## ADDED Requirements

### Requirement: 过期 lease 必须被原子恢复

系统 MUST 只扫描 active Attempt 的 lease 已到期且 Task 处于 `running` 或 `cancel_requested` 的候选。恢复 MUST 在同一事务内结束失效 Attempt、写入唯一恢复 Event 和命令回执，并按既有尝试次数与取消状态将 Task 转为 `cancelled`、`queued`、`retry_wait` 或 `failed`。

#### Scenario: 恢复普通过期任务

- **WHEN** 恢复器发现 `running` Task 的 active lease 已到期且仍有剩余尝试次数
- **THEN** 系统将 Attempt 标记为 expired 并记录恢复事实
- **AND** Task 按退避策略进入 `queued` 或 `retry_wait`，等待新的 Worker 领取

#### Scenario: 恢复取消中的过期任务

- **WHEN** `cancel_requested` Task 的 active lease 到期
- **THEN** 系统结束该 Attempt 并将 Task 转为 `cancelled`
- **AND** 不创建新的 active Attempt 或重新入队

#### Scenario: 恢复耗尽尝试的任务

- **WHEN** 过期 Attempt 已使 Task 达到最大尝试次数
- **THEN** 系统将 Task 转为 `failed` 并使用安全的 `LEASE_EXPIRED` 失败码
- **AND** 不保存 lease token、输入原文或完整异常

### Requirement: 多个恢复器不得重复恢复同一 Attempt

恢复候选选择 MUST 使用数据库锁和跳过已锁定行的并发语义。相同恢复命令重放 MUST 返回当前 Task 结果，不得重复结束 Attempt、追加恢复 Event 或创建命令回执。

#### Scenario: 并发恢复竞争

- **WHEN** 两个独立恢复器同时扫描同一过期 Attempt
- **THEN** 最多一个事务完成恢复状态转换
- **AND** 另一个事务得到空结果、当前结果或稳定幂等结果

#### Scenario: 重启后重放恢复命令

- **WHEN** 进程重启后以相同 Task、Attempt 和恢复命令 ID 再次处理
- **THEN** 系统返回已恢复的当前状态
- **AND** 不追加第二条恢复 Event 或第二个命令回执

### Requirement: 退避到期任务必须自动重新入队

系统 MUST 只处理 `retry_wait` 且 `available_at <= now` 的 Task，并通过既有 `requeue_due` 规则将其转为 `queued`。重入队 MUST 保留尝试历史和事件顺序，并具备稳定命令幂等；退避未到期的 Task 不得被提前执行。

#### Scenario: 退避到期重新入队

- **WHEN** 重试调度器扫描到达 `available_at` 的 `retry_wait` Task
- **THEN** Task 转为 `queued` 并记录唯一重入队 Event
- **AND** 下一次 Worker 轮询可以领取该 Task

#### Scenario: 退避尚未到期

- **WHEN** 重试调度器扫描 `available_at > now` 的 `retry_wait` Task
- **THEN** 调度器跳过该 Task
- **AND** Task 状态、Attempt 和 Event 保持不变

### Requirement: 取消必须遵循协作式停止

系统 MUST 对 `queued` 或 `retry_wait` Task 直接写入 `cancelled`；对 `running` Task 只写入 `cancel_requested` 并保留 active Attempt。只有持有有效 lease 的执行器在安全检查点确认停止后，系统才能将 Task 转为 `cancelled`；调度器不得强杀线程或外部 Provider。

#### Scenario: 取消排队任务

- **WHEN** 受信任取消协调器请求取消 `queued` Task
- **THEN** Task 转为 `cancelled` 并记录取消 Event
- **AND** 不创建或修改 Attempt

#### Scenario: 请求取消运行中任务

- **WHEN** 受信任取消协调器请求取消 `running` Task
- **THEN** Task 转为 `cancel_requested` 并保留 active Attempt
- **AND** Worker 可以在安全检查点观察取消信号

#### Scenario: 执行器确认取消

- **WHEN** 持有有效 lease 的执行器确认已停止 `cancel_requested` Task
- **THEN** Attempt 结束并将 Task 转为 `cancelled`
- **AND** 后续 Worker 不再领取该 Task

### Requirement: 手动重试必须受策略和幂等约束

系统 MUST 只允许服务端受信任 Application 对策略允许且未耗尽尝试次数的 `failed` Task 发起手动重试。相同 command_id 重放 MUST 返回当前结果，不得重复追加重试 Event；不允许的主体、状态或策略 MUST 得到稳定错误。

#### Scenario: 手动重试失败任务

- **WHEN** 受信任调度器以新 command_id 重试允许手动重试的 `failed` Task
- **THEN** Task 转为 `queued` 并记录唯一手动重试 Event
- **AND** Worker 可以按正常流程领取新的 Attempt

#### Scenario: 手动重试不被策略允许

- **WHEN** 调度器请求重试 `allow_manual_retry = false` 或已耗尽尝试次数的 Task
- **THEN** 系统拒绝命令并保持 Task、Attempt 和 Event 不变

#### Scenario: 重放手动重试命令

- **WHEN** 进程重启后以相同 Task 和 command_id 重放已处理的手动重试
- **THEN** 系统返回当前 `queued` 或执行中状态
- **AND** 不追加第二条重试 Event 或回执

### Requirement: 调度失败不得泄漏敏感数据或污染其他候选

恢复、重入队、取消和手动重试调度 MUST 使用安全错误码隔离单个候选失败。日志、Event 和错误投影不得包含 lease token、输入指纹、原始输入、Provider 凭据、完整异常或原始响应；一个候选的事务失败 MUST 回滚其全部变化而不阻塞后续候选。

#### Scenario: 单候选事务失败

- **WHEN** 批量调度中的一个候选在写入状态、Event 或命令回执时失败
- **THEN** 系统回滚该候选的全部持久化变化并记录固定错误码
- **AND** 调度器继续处理其他候选

#### Scenario: 敏感错误被脱敏

- **WHEN** 恢复器或重试调度器捕获包含 token、输入或完整异常的底层错误
- **THEN** 对外和日志只返回安全分类代码
- **AND** 敏感内容不进入 TaskView、Event 或命令回执
