## Purpose

定义经授权的 Agent Call 如何按服务端异步档案受控提交为 Task、保持幂等并返回不透明执行引用。
## Requirements
### Requirement: 只有已授权且登记异步档案的 Agent 能力可以桥接 Task

系统 MUST 在既有目录、主体、输入和确认策略均通过后，重新读取当前能力条目，并仅允许服务端异步档案注册表中登记且与该条目一致的 `agent` 能力进入 Task 桥接。客户端、模型输出和协议适配器 MUST NOT 通过输入字段选择异步模式、Task 类型或执行器；业务输入中的同名字段不得被解释为 Task 控制字段。

#### Scenario: 已授权异步能力进入桥接

- **WHEN** 结构化 Agent 调用已通过 Dispatcher 的目录、主体、输入和确认复核，且当前能力存在匹配的服务端异步档案
- **THEN** 系统将调用交给 Agent→Task 桥接
- **AND** 桥接只使用服务端档案和可信主体，不读取客户端提供的 Task 策略

#### Scenario: 未登记异步能力继续同步执行

- **WHEN** 调用已授权但能力没有异步档案
- **THEN** 系统调用既有同步策略且不创建 Task、Attempt、Event 或提交回执
- **AND** 同步结果保持现有 `completed` 或受控失败语义

#### Scenario: 已登记档案与目录不一致

- **WHEN** 调用命中异步档案，但当前目录条目已失效、类型不符或与档案绑定不一致
- **THEN** 系统不创建 Task、Attempt、Event 或提交回执
- **AND** 系统返回稳定的配置或能力不可用错误，不得降级为同步执行

#### Scenario: 授权失败先于桥接

- **WHEN** 能力不存在、已禁用、主体无权、输入无效或确认未满足
- **THEN** 系统返回既有受控分发结果
- **AND** 桥接与受信任 Task 提交服务均不被调用

### Requirement: Task 桥接必须使用服务端固定提交档案

系统 MUST 通过既有受信任 Task 提交 Application 创建异步 Task。异步档案 MUST 固定 `task_type`、最大尝试次数、手动重试策略和展示字段白名单；调用方不得覆盖 owner、Task 策略、执行器地址或展示字段范围。若输入快照事实包含 `snapshot_reference`，桥接 MUST 仅将其作为档案允许的内部执行元数据传递给受信任 Worker，且不得进入 TaskView、事件元数据或公开协议响应。

#### Scenario: 桥接创建受控排队任务

- **WHEN** 已授权异步调用产生有效的快照事实和展示摘要
- **THEN** 系统以可信主体 subject 作为 owner，按档案固定策略提交一个 `queued` Task
- **AND** 返回安全 Task 状态所需的 opaque execution reference
- **AND** 返回值不包含输入指纹、原始输入、lease 或 Executor 对象

#### Scenario: 快照引用只进入内部执行上下文

- **WHEN** 快照事实包含服务端生成的 opaque `snapshot_reference`
- **THEN** 桥接将引用交给受信任提交能力的白名单内部元数据
- **AND** TaskView、生命周期事件和 Agent Dispatch 响应均不返回该引用

#### Scenario: 调用输入不得覆盖档案字段

- **WHEN** 调用输入包含与 task type、owner、max attempts、retry policy、executor 或展示字段同名的业务字段
- **THEN** 系统不将其解释为 Task 控制参数，也不允许其覆盖服务端档案
- **AND** Task 仍只使用档案固定策略和档案生成的允许展示摘要

### Requirement: Agent 到 Task 桥接必须保持调用幂等

系统 MUST 使用规范化的能力代码和稳定 `call_id` 生成桥接幂等键，并将输入快照规范化产生的指纹交给受信任 Task 提交能力。相同主体、能力和调用标识的重放 MUST 返回同一 Task 引用；同一幂等键对应不同指纹 MUST 返回稳定冲突。

#### Scenario: 重放同一个异步 Agent 调用

- **WHEN** 同一已认证主体以相同能力代码、`call_id` 和输入指纹重复提交
- **THEN** 系统返回首次创建的 Task execution reference 和当前安全状态
- **AND** 不创建第二个 Task、Attempt、Event 或创建回执

#### Scenario: 同一调用标识使用不同输入

- **WHEN** 同一主体和能力使用同一 `call_id`，但快照指纹与首次提交不同
- **THEN** 系统返回稳定的幂等冲突错误
- **AND** 原 Task 的状态、输入指纹和事件历史保持不变

#### Scenario: 快照规范化失败

- **WHEN** 异步档案绑定的输入快照 Port 无法校验或生成确定性指纹
- **THEN** 系统返回受控输入错误
- **AND** 不调用受信任 Task 提交服务

### Requirement: 异步桥接结果必须是受控的已接收引用

系统 MUST 将成功的 Task 提交转换为 `accepted` 执行结果，并返回不透明 execution reference。桥接失败、Task 提交冲突、能力失效或依赖未配置时 MUST 返回稳定错误，不得同时返回已接收引用和同步输出。

#### Scenario: Task 提交成功

- **WHEN** 受信任提交服务创建或幂等返回一个 Task
- **THEN** Agent 执行策略返回 `accepted`
- **AND** execution reference 与原始 `call_id`、能力代码及主体调用上下文保持关联

#### Scenario: Task 提交失败

- **WHEN** 受信任提交服务拒绝主体、档案或幂等冲突，或发生受控持久化失败
- **THEN** Agent 执行策略返回稳定错误码和安全消息
- **AND** 结果不包含 Task ID、输入指纹、lease 或底层异常原文

### Requirement: 桥接保持公开协议和同步路径隔离

系统 MUST 将 Agent→Task 桥接保持为服务端内部 Application/Port 能力。该 Change 不得新增浏览器、HTTP、MCP 或 Function Calling 的通用 Task 创建入口；未登记异步档案的既有同步能力 MUST 继续执行原同步策略且不得创建 Task。

#### Scenario: 检查公开接口边界

- **WHEN** 开发者检查 HTTP、MCP、Function Calling 和浏览器路由
- **THEN** 不存在可由调用方提交任意 Task type、Executor、owner 或重试策略的创建协议
- **AND** 异步提交只能从已授权 Agent 分发内部触发

#### Scenario: 同步能力保持原行为

- **WHEN** 已授权 Agent 能力没有异步档案并使用默认同步执行策略
- **THEN** 系统返回既有 `completed` 或受控失败结果
- **AND** 不创建 Task 或写入 Task 存储

