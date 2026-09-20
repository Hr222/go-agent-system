## MODIFIED Requirements

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
