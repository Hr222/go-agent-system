# task-lifecycle-management Specification

## Purpose
TBD - created by archiving change introduce-task-management. Update Purpose after archive.
## Requirements
### Requirement: Task 领域对象必须具备稳定生命周期事实

系统 SHALL 定义 Task、Attempt、Event 三类领域对象及其关系。Task MUST 保存稳定标识、task type、owner、状态、时间、输入指纹、尝试限制和可展示元数据；一个 Task 可以有多个 Attempt，但同一时刻最多只能有一个 active Attempt；每次状态转换 MUST 产生唯一 transition_id 和递增事件事实。

#### Scenario: 创建任务形成初始事实
- **WHEN** 受信任 Application 提交已校验的 task type、owner、输入指纹和幂等键
- **THEN** 领域创建稳定 task ID，初始状态为 `queued`
- **AND** 产生一条 `TASK_CREATED` 事件事实，且不创建 Attempt

#### Scenario: 领域对象拒绝无效任务身份
- **WHEN** 创建命令缺少 owner、task type、幂等键或输入指纹
- **THEN** 领域拒绝创建
- **AND** 不产生 Task、Attempt 或 Event

### Requirement: 任务命令必须幂等

系统 MUST 为创建、领取、续租、取消、手动重试和终态提交定义稳定幂等依据。相同命令重放 MUST 返回原结果或当前结果，不得重复创建 Attempt 或重复追加同一 transition_id 的事件；同一创建幂等键对应不同输入指纹 MUST 返回稳定冲突。

#### Scenario: 网络重试提交同一任务
- **WHEN** 同一 owner 以相同 task type、幂等键和输入指纹重复提交
- **THEN** 系统返回第一次创建的 task ID 与当前状态
- **AND** 系统不新增 Task、Attempt 或 Event

#### Scenario: 幂等键复用不同输入
- **WHEN** 同一 owner 和 task type 使用已存在的幂等键但输入指纹不同
- **THEN** 系统拒绝提交并说明幂等键冲突
- **AND** 系统不修改原 Task

#### Scenario: 重复领取同一命令
- **WHEN** 同一个 worker 使用相同 task ID、worker ID 和 claim ID 重复领取
- **THEN** 系统返回第一次创建的 Attempt
- **AND** 不创建第二个 Attempt 或重复 `TASK_CLAIMED` 事件

#### Scenario: 重放成功提交
- **WHEN** 持有有效 lease 的执行器以相同 attempt ID、lease token 和结果指纹重复提交成功
- **THEN** 系统返回原成功结果
- **AND** 不重复修改状态或追加成功事件

### Requirement: 任务状态机必须限制合法迁移

系统 SHALL 只使用 `queued`、`running`、`retry_wait`、`cancel_requested`、`succeeded`、`failed` 和 `cancelled` 状态。Task MUST 从 `queued` 被领取为 `running`，并只能由持有有效 lease 的执行者写入成功、失败、重试等待或取消终态；`succeeded`、`failed` 和 `cancelled` 为终态，普通领取流程不得重新执行它们。

#### Scenario: Worker 成功完成已领取任务
- **WHEN** 执行者持有 `running` Task 的有效 lease 并提交安全结果摘要
- **THEN** 系统将 Task 转为 `succeeded` 并记录完成 Attempt/Event
- **AND** 后续普通领取不再执行该 Task

#### Scenario: 过期执行者尝试写入结果
- **WHEN** 执行者的 lease token 已过期、被恢复或不再匹配当前 Task
- **THEN** 系统拒绝该执行者的状态更新
- **AND** 该更新不得覆盖当前 Attempt、结果或状态

#### Scenario: 拒绝非法状态迁移
- **WHEN** 调用方尝试从 `succeeded`、`failed` 或 `cancelled` 普通领取、取消或提交结果
- **THEN** 系统返回稳定的非法迁移错误
- **AND** Task、Attempt 和 Event 均保持不变

### Requirement: Attempt 生命周期必须保持唯一 active 尝试

领域层 MUST 要求 `queued` Task 领取后创建一个 active Attempt，并将 Task 转为 `running`；`running` 或 `cancel_requested` 状态下不得再创建第二个 active Attempt。lease token 和租约时钟字段属于 Attempt 的执行事实，过期判断和并发原子性留给后续基础设施 Change。

#### Scenario: 领取创建唯一 Attempt
- **WHEN** `queued` Task 被合法领取
- **THEN** Task 转为 `running` 并创建一个 active Attempt
- **AND** 事件记录 claim_id、worker_id 的安全元数据

#### Scenario: 运行中任务不能重复创建 active Attempt
- **WHEN** `running` 或 `cancel_requested` Task 再次执行新的领取命令
- **THEN** 系统拒绝该领取
- **AND** 原 active Attempt 保持不变

### Requirement: 取消、重试与恢复必须保留执行事实

系统 MUST 对 `queued` 或 `retry_wait` Task 直接写入 `cancelled`；对 `running` Task 写入 `cancel_requested`，直到执行者确认停止后才写入 `cancelled`。可重试失败 MUST 先进入 `retry_wait` 并在可执行时间到达后回到 `queued`；耗尽尝试或不可重试失败 MUST 进入 `failed`。手动重试只允许受策略许可的 `failed` Task。租约过期后，系统 MUST 记录恢复事件，并根据取消状态和剩余尝试次数将 Task 转为 `cancelled`、`queued` 或 `failed`。

#### Scenario: 取消排队任务
- **WHEN** owner 取消一个 `queued` Task
- **THEN** 系统将其转为 `cancelled` 并记录取消事件
- **AND** 不创建或修改 Attempt

#### Scenario: 取消运行中任务
- **WHEN** owner 取消一个 `running` Task
- **THEN** 系统将其转为 `cancel_requested` 并保留 active Attempt
- **AND** 仅在执行者确认停止后将其转为 `cancelled`

#### Scenario: 瞬时失败等待重试
- **WHEN** 有效 lease 的执行者报告可重试失败且未耗尽最大尝试数
- **THEN** 系统记录该 Attempt 的安全失败分类并将 Task 转为 `retry_wait`
- **AND** 退避到期后以新的事件将 Task 重新入队

#### Scenario: 失效执行被恢复
- **WHEN** `running` Task 的租约过期且没有有效续租
- **THEN** 系统记录失效 Attempt 和恢复事件
- **AND** 系统根据剩余尝试次数及取消状态安全地重新排队、失败或取消该 Task

### Requirement: 任务历史必须可审计且不泄漏敏感数据

系统 MUST 为创建、领取、开始、取消请求、重试调度、恢复、成功、失败和取消终态记录按单 Task 递增的事件序列。事件和失败说明 MUST 仅保存安全分类、代码和可展示摘要，不得包含原始输入、Provider 凭据、完整异常或原始响应。

#### Scenario: 查询任务审计历史
- **WHEN** 调用方读取一个 Task 的事件历史
- **THEN** 系统按递增 sequence 返回生命周期事实
- **AND** 返回内容不包含输入原文、lease token 或底层异常文本
