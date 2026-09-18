## ADDED Requirements

### Requirement: 任务生命周期事实必须可持久恢复

系统 MUST 将 Task、Attempt、Event 和已处理命令的幂等事实持久化到 PostgreSQL。重新创建 Repository 或进程重启后，系统 MUST 能按稳定 Task ID 恢复相同状态、尝试顺序、事件顺序、时间和安全结果摘要；持久化不得把 lease token、输入指纹或原始异常写入 Event 或安全状态投影。

#### Scenario: 重启后恢复任务聚合
- **WHEN** 系统持久化一个包含 Attempt 和 Event 的 Task 后使用新 Repository 读取该 Task
- **THEN** 系统恢复相同的 Task 状态、按序 Attempt 和按序 Event
- **AND** 恢复后的安全状态投影不包含 lease token 或输入指纹

#### Scenario: 读取不存在的任务
- **WHEN** 调用方读取未持久化的 Task ID
- **THEN** 系统返回未找到结果
- **AND** 不创建 Attempt、Event 或命令回执

### Requirement: 持久化命令必须原子地保持幂等

系统 MUST 在同一数据库事务内写入 Task 聚合变化、对应 Event 和适用的命令回执。提交 Task 的唯一键、领取标识、终态结果指纹和已处理命令必须在进程重启和并发调用后继续产生 TM-01 定义的原结果或稳定冲突，不得重复创建 Attempt 或 Event。

#### Scenario: 并发重放同一提交
- **WHEN** 两个独立数据库事务以相同 owner、task type、幂等键和输入指纹提交 Task
- **THEN** 系统只持久化一个 Task 和一条创建 Event
- **AND** 两个调用都取得该 Task 的稳定标识

#### Scenario: 重启后重放已处理取消命令
- **WHEN** 系统完成取消命令并在新 Repository 中以相同 Task ID 和命令标识重放
- **THEN** 系统返回当前取消状态
- **AND** 不追加第二条取消 Event 或第二条命令回执

#### Scenario: 事务失败不保留部分任务事实
- **WHEN** 写入 Task 状态、Event 或命令回执的同一事务发生失败
- **THEN** 系统回滚该次命令的全部持久化变化
- **AND** 后续读取不会观察到孤立 Attempt、Event 或命令回执

### Requirement: 持久化层必须强制任务聚合关系不变量

系统 MUST 通过 PostgreSQL 约束和锁保护 Task、Attempt、Event 的关系不变量：Task 提交键唯一、Attempt 序号和领取标识唯一、Event 序号和转换标识唯一，以及同一 Task 至多一个 active Attempt。持久化层不得接受引用不存在 Task 的子事实或不符合领域安全 JSON 形状的 Event。

#### Scenario: 并发领取不能产生两个活动尝试
- **WHEN** 两个独立数据库事务竞争领取同一个 queued Task
- **THEN** 最多一个事务持久化 active Attempt 和领取 Event
- **AND** 另一事务取得稳定的重放结果或非法状态转换错误

#### Scenario: 数据库拒绝重复或孤立事实
- **WHEN** 调用方尝试写入重复 Attempt/Event 序号、重复转换标识、第二个 active Attempt 或引用不存在 Task 的子事实
- **THEN** 持久化层拒绝该写入
- **AND** 已持久化的 Task 聚合保持可恢复和一致
