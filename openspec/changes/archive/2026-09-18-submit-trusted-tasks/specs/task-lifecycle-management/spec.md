## MODIFIED Requirements

### Requirement: Task 领域对象必须具备稳定生命周期事实

系统 SHALL 定义 Task、Attempt、Event 三类领域对象及其关系。Task MUST 保存稳定标识、task type、owner、状态、时间、输入指纹、尝试限制和可展示元数据；一个 Task 可以有多个 Attempt，但同一时刻最多只能有一个 active Attempt；每次状态转换 MUST 产生唯一 transition_id 和递增事件事实。合法领取 MUST 原子地创建 Attempt、将 Task 迁移为 `running`，并以一条 `TASK_CLAIMED` 事件同时记录领取和开始执行事实。Task 创建 MUST 通过已注册的受信任 Application 提交能力进入生命周期；该能力从可信主体确定 owner，并以服务端固定策略确定 task type 和尝试限制。

#### Scenario: 创建任务形成初始事实
- **WHEN** 受信任 Application 以可信主体、已校验的输入指纹和幂等键提交任务
- **THEN** 领域创建稳定 task ID，初始状态为 `queued`
- **AND** 产生一条 `TASK_CREATED` 事件事实，且不创建 Attempt

#### Scenario: 合法领取同时开始执行
- **WHEN** `queued` Task 被合法领取
- **THEN** 系统创建唯一 active Attempt 并将 Task 转为 `running`
- **AND** 系统只产生一条 `TASK_CLAIMED` 事件作为领取和开始执行的审计事实

#### Scenario: 领域对象拒绝无效任务身份
- **WHEN** 创建命令缺少 owner、task type、幂等键或输入指纹
- **THEN** 领域拒绝创建
- **AND** 不产生 Task、Attempt 或 Event
