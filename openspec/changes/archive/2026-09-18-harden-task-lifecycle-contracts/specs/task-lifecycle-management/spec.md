## MODIFIED Requirements

### Requirement: Task 领域对象必须具备稳定生命周期事实

系统 SHALL 定义 Task、Attempt、Event 三类领域对象及其关系。Task MUST 保存稳定标识、task type、owner、状态、时间、输入指纹、尝试限制和可展示元数据；一个 Task 可以有多个 Attempt，但同一时刻最多只能有一个 active Attempt；每次状态转换 MUST 产生唯一 transition_id 和递增事件事实。合法领取 MUST 原子地创建 Attempt、将 Task 迁移为 `running`，并以一条 `TASK_CLAIMED` 事件同时记录领取和开始执行事实。

#### Scenario: 创建任务形成初始事实
- **WHEN** 受信任 Application 提交已校验的 task type、owner、输入指纹和幂等键
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

### Requirement: 任务历史必须可审计且不泄漏敏感数据

系统 MUST 为创建、领取即开始、取消请求、重试调度、恢复、成功、失败和取消终态记录按单 Task 递增的事件序列。每条事件元数据 MUST 仅使用该事件类型允许的安全字段，并且 MUST 是可由标准 JSON 编码的有限标量；事件和失败说明不得包含原始输入、lease token、Provider 凭据、完整异常或原始响应。

#### Scenario: 查询任务审计历史
- **WHEN** 调用方读取一个 Task 的事件历史
- **THEN** 系统按递增 sequence 返回生命周期事实
- **AND** 返回内容不包含输入原文、lease token 或底层异常文本

#### Scenario: 拒绝不安全或非标准 JSON 的事件元数据
- **WHEN** 领域接收含未知字段、敏感字段、非有限浮点数或不符合安全格式的代码/指纹的事件元数据
- **THEN** 系统拒绝创建该事件
- **AND** 不将该数据作为生命周期审计事实保存

## ADDED Requirements

### Requirement: 安全任务投影必须与执行器 lease 分离

系统 MUST 将 Task 的安全状态投影与仅供受信任执行器使用的 lease 契约分离。安全 Task 投影不得包含输入指纹、lease token 或 Attempt 内部执行事实；领取和续租产生的 lease 只能由受信任执行器边界消费，不能作为通用 Application 或协议响应暴露。

#### Scenario: 读取安全 Task 状态
- **WHEN** 调用方取得 Task 的安全状态投影
- **THEN** 投影包含 Task 状态和可展示字段
- **AND** 投影不包含输入指纹、lease token 或 Attempt 内部字段

#### Scenario: 受信任执行器领取任务
- **WHEN** 受信任执行器提交合法领取命令
- **THEN** 系统在执行器内部契约中返回该 Attempt 的 lease
- **AND** 不创建可供通用协议或状态查询复用的含 token 投影
