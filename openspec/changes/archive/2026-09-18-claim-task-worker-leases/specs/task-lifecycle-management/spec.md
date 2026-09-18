# task-lifecycle-management Specification

## MODIFIED Requirements

### Requirement: Task 领域对象必须具备稳定生命周期事实

系统 SHALL 定义 Task、Attempt、Event 三类领域对象及其关系。Task MUST 保存稳定标识、task type、owner、状态、时间、输入指纹、尝试限制和可展示元数据；一个 Task 可以有多个 Attempt，但同一时刻最多只能有一个 active Attempt；每次状态转换 MUST 产生唯一 transition_id 和递增事件事实。Task 创建 MUST 通过已注册的受信任 Application 提交能力进入生命周期，该能力从可信主体确定 owner，并以服务端固定策略确定 task type 和尝试限制。Worker 的合法领取 MUST 只选择可执行的 `queued` Task，并以原子事务创建 Attempt、将 Task 迁移为 `running`，以一条 `TASK_CLAIMED` 事件同时记录领取和开始执行事实。

#### Scenario: 创建任务形成初始事实

- **WHEN** 受信任 Application 以可信主体、已校验的输入指纹和幂等键提交任务
- **THEN** 领域创建稳定 task ID，初始状态为 `queued`
- **AND** 产生一条 `TASK_CREATED` 事件事实，且不创建 Attempt

#### Scenario: Worker 合法领取同时开始执行

- **WHEN** 受信任 Worker 领取一个可执行的 `queued` Task
- **THEN** 系统在同一持久化事务中创建唯一 active Attempt 并将 Task 转为 `running`
- **AND** 系统只产生一条 `TASK_CLAIMED` 事件作为领取和开始执行的审计事实

#### Scenario: 领域对象拒绝无效任务身份

- **WHEN** 创建命令缺少 owner、task type、幂等键或输入指纹
- **THEN** 领域拒绝创建
- **AND** 不产生 Task、Attempt 或 Event

### Requirement: 任务命令必须幂等

系统 MUST 为创建、领取、续租、取消、手动重试和终态提交定义稳定幂等依据。相同命令重放 MUST 返回原结果或当前结果，不得重复创建 Attempt 或重复追加同一 transition_id 的事件；同一创建幂等键对应不同输入指纹 MUST 返回稳定冲突。Worker 的竞争领取和执行结果写回也 MUST 在进程重启及并发调用后保持相同的重放或稳定冲突语义。

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

#### Scenario: 并发 Worker 重复领取

- **WHEN** 两个独立 Worker 以不同领取命令竞争同一个 `queued` Task
- **THEN** 最多一个命令创建 Attempt 并返回 lease
- **AND** 另一个命令不创建第二个 Attempt 或重复 `TASK_CLAIMED` 事件

#### Scenario: 重放成功提交

- **WHEN** 持有有效 lease 的执行器以相同 attempt ID、lease token 和结果指纹重复提交成功
- **THEN** 系统返回原成功结果
- **AND** 不重复修改状态或追加成功事件

### Requirement: Attempt 生命周期必须保持唯一 active 尝试

领域层 MUST 要求可执行的 `queued` Task 领取后创建一个 active Attempt，并将 Task 转为 `running`；`running` 或 `cancel_requested` 状态下不得再创建第二个 active Attempt。Worker 和持久化层 MUST 以原子锁定保护该不变量。lease token、租约时钟和 renewal sequence 属于 Attempt 的受信任执行事实；过期、token 匹配和续租顺序 MUST 在 Worker/Lifecycle 边界校验。

#### Scenario: 领取创建唯一 Attempt

- **WHEN** Worker 合法领取一个可执行的 `queued` Task
- **THEN** Task 转为 `running` 并创建一个 active Attempt
- **AND** 事件记录 claim_id、worker_id 的安全元数据

#### Scenario: 运行中任务不能重复创建 active Attempt

- **WHEN** `running` 或 `cancel_requested` Task 再次执行新的领取命令
- **THEN** 系统拒绝该领取
- **AND** 原 active Attempt 保持不变

#### Scenario: 续租必须保持单调

- **WHEN** Worker 使用匹配的 active Attempt 和 lease token 提交不大于当前值的 renewal sequence
- **THEN** 系统拒绝续租
- **AND** Attempt 的到期时间和 sequence 保持不变

### Requirement: 持久化层必须强制任务聚合关系不变量

系统 MUST 通过 PostgreSQL 约束、父 Task 行锁和原子候选选择保护 Task、Attempt、Event 的关系不变量：Task 提交键唯一、Attempt 序号和领取标识唯一、Event 序号和转换标识唯一，以及同一 Task 至多一个 active Attempt。持久化层不得接受引用不存在 Task 的子事实或不符合领域安全 JSON 形状的 Event；竞争 Worker 不得通过先查后写绕过这些不变量。

#### Scenario: 并发领取不能产生两个活动尝试

- **WHEN** 两个独立数据库事务竞争领取同一个 queued Task
- **THEN** 最多一个事务持久化 active Attempt 和领取 Event
- **AND** 另一事务取得稳定的空结果、重放结果或非法状态转换错误

#### Scenario: 数据库拒绝重复或孤立事实

- **WHEN** 调用方尝试写入重复 Attempt/Event 序号、重复转换标识、第二个 active Attempt 或引用不存在 Task 的子事实
- **THEN** 持久化层拒绝该写入
- **AND** 已持久化的 Task 聚合保持可恢复和一致
