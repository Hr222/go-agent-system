# task-worker-execution Specification

## Purpose

定义受信任 Task Worker 的原子领取、lease 续租、固定执行器绑定和安全结果回写边界，限制其只能通过服务端内部应用契约运行。

## Requirements

### Requirement: Worker 必须从受信任边界运行

系统 MUST 只允许由服务端 Composition Root 注册的 Worker 和执行器访问领取、续租及含 lease 的执行器契约。系统 MUST 不为这些契约新增浏览器、公开 HTTP、MCP 或 Function Calling 入口；安全 Task 投影和普通状态查询 MUST 不包含 lease。

#### Scenario: 未注册执行器不能领取任务

- **WHEN** Worker 使用未在服务端固定注册表中的 task type 请求执行
- **THEN** 系统不把任务交给未知执行器
- **AND** 返回不含 token、输入或完整异常的稳定错误，并保持任务事实一致

#### Scenario: 普通状态读取不暴露 lease

- **WHEN** 调用方读取已领取 Task 的安全状态
- **THEN** 返回状态和可展示字段
- **AND** 返回内容不包含 lease token、Attempt 内部字段或输入指纹

### Requirement: Worker 领取必须是原子且唯一的

Worker MUST 只能领取当前可执行的 `queued` Task。领取选择、Attempt 创建、Task 转为 `running` 和唯一 `TASK_CLAIMED` Event MUST 在同一个持久化事务内完成；并发 Worker 对同一 Task 最多一个成功领取者，未选中的 Worker MUST 得到空结果或稳定的竞争结果。

#### Scenario: Worker 领取排队任务

- **WHEN** Worker 请求领取一个 `queued` 且已到执行时间的 Task
- **THEN** 系统创建一个 active Attempt，签发内部 lease，并将 Task 转为 `running`
- **AND** 只追加一条 `TASK_CLAIMED` Event 作为领取和开始执行事实

#### Scenario: 并发 Worker 竞争同一任务

- **WHEN** 两个独立 Worker 同时领取同一个可执行 Task
- **THEN** 最多一个 Worker 获得 active Attempt 和 lease
- **AND** 不产生第二个 Attempt 或第二条 `TASK_CLAIMED` Event

#### Scenario: 没有可执行任务

- **WHEN** Worker 轮询时不存在满足条件的 `queued` Task
- **THEN** 系统返回空轮询结果
- **AND** 不创建 Task、Attempt、Event 或命令回执

### Requirement: Lease 必须可续租且严格校验

系统 MUST 在受信任 Worker 内生成不可预测、具有未来到期时间的 lease。续租 MUST 携带当前 Attempt、匹配 token 和严格递增的 renewal sequence；完成、失败或取消确认 MUST 拒绝过期、非 active 或 token 不匹配的 lease，并且不得修改 Task、Attempt 或 Event。

#### Scenario: Worker 正常续租

- **WHEN** active Attempt 持有匹配 token 并提交大于当前值的 renewal sequence 与更晚到期时间
- **THEN** 系统更新该 Attempt 的租约时间和 sequence
- **AND** 返回更新后的内部 lease，不追加与状态转换无关的生命周期 Event

#### Scenario: 旧 token 写回结果

- **WHEN** 执行器使用已过期、已替换或不匹配当前 Attempt 的 token 完成任务
- **THEN** 系统拒绝结果写回并返回稳定的 lease 无效错误
- **AND** 当前 Task、Attempt、结果和 Event 保持不变

#### Scenario: 重复续租命令

- **WHEN** Worker 使用相同 Attempt、token 和已处理的 renewal sequence 重放续租
- **THEN** 系统返回已有的租约结果或稳定的幂等结果
- **AND** 不把租约时间倒退或重复追加事实

### Requirement: Worker 必须通过固定执行器完成结果回写

Worker MUST 根据服务端固定的 task type 绑定选择执行器，并将成功结果通过既有生命周期 Application 提交为 `succeeded`，将受控失败通过既有失败命令提交为 `retry_wait` 或 `failed`。执行器不得直接修改 Repository、Domain 或数据库；结果摘要和失败代码 MUST 遵守任务安全数据规则。

#### Scenario: 执行器成功完成任务

- **WHEN** 已领取执行器返回安全结果指纹和摘要，且 lease 仍有效
- **THEN** 系统将 Task 转为 `succeeded` 并记录完成 Attempt/Event
- **AND** 后续普通 Worker 领取不再执行该 Task

#### Scenario: 执行器拒绝或抛出异常

- **WHEN** 已注册执行器拒绝任务或发生运行时异常
- **THEN** Worker 使用固定失败分类和安全错误代码调用失败命令
- **AND** 不保存原始异常、输入、Provider 响应或 lease token

#### Scenario: 重放相同执行结果

- **WHEN** Worker 以相同 Attempt、token 和结果指纹重放已处理的成功或失败结果
- **THEN** 系统返回原状态或当前结果
- **AND** 不重复追加终态 Event 或覆盖已有安全摘要

### Requirement: 单次执行失败不得污染后续轮询

Worker MUST 将一次领取的执行、续租和结果提交限制在该 Task 的执行上下文内。执行器异常、结果提交失败或 lease 失效 MUST 结束当前执行并释放进程内资源，不能让异常跨越到下一次轮询，也不能伪造恢复、取消或重试调度事实。

#### Scenario: 结果提交失败后继续轮询

- **WHEN** 执行器完成但结果提交因数据库或 lease 错误失败
- **THEN** Worker 记录固定安全错误并结束当前执行
- **AND** 下一次轮询仍能独立运行，不创建额外 Attempt 或伪造成功 Event

#### Scenario: Worker 崩溃留下过期租约

- **WHEN** Worker 在 Task 执行期间停止且未完成续租
- **THEN** Task 保留当前 `running` 和 lease 到期事实
- **AND** 本 Change 不自动恢复、取消或重新排队该 Task
