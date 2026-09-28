## MODIFIED Requirements

### Requirement: Run 与 Node Run 必须使用受控状态和依赖语义

系统 MUST 为 Run 和 Node Run 定义稳定状态、尝试序号和有序安全事件。Run 至少支持 `queued`、`running`、`accepted`、`succeeded`、`failed`、`cancel_requested` 和 `cancelled`；Node Run 支持上述执行状态以及 `skipped`。节点只有在所有前置节点成功且边引用的安全输出引用真实可用时才可进入执行边界；节点适配器不得直接修改 Run、Node Run 或事件。

#### Scenario: 前置节点未完成时保持排队

- **WHEN** Workflow Run 中某节点仍有未成功的前置节点
- **THEN** 该节点保持 `queued` 或以安全查询结果标记为未就绪
- **AND** 系统不创建该节点的执行尝试或调用能力处理器

#### Scenario: 前置节点成功且输出引用可用后节点可执行

- **WHEN** 某节点全部前置节点成功，且每条边引用的输出字段都存在于对应前置节点的安全成功事实中
- **THEN** Application 将该节点交给受控 Node Executor Port
- **AND** 节点执行使用固定 Version 能力绑定、可信主体和前置节点记录的不透明输出引用
- **AND** 调用方不能用另一值覆盖由边提供的输入

#### Scenario: 前置节点成功但安全输出引用缺失

- **WHEN** 某节点的前置节点已成功，但边引用的一个或多个输出字段没有安全成功事实
- **THEN** 该节点保持 `queued` 或以安全查询结果标记为未就绪
- **AND** 系统不创建该节点的执行尝试或调用能力处理器

#### Scenario: 异步节点被接收

- **WHEN** Node Executor 返回 `accepted` 和不透明 execution reference
- **THEN** Node Run 记录 `accepted` 状态与该引用，Workflow Run 不伪报为成功
- **AND** 事件不包含 lease、原始输入、Provider 响应或下载地址

### Requirement: Workflow 取消、失败和重试必须可控且幂等

系统 MUST 通过 Application 命令执行 Run/Node 的取消、失败和受策略约束的重试。运行中的 Run 取消只能先进入 `cancel_requested`，并通过 Node Executor Port 请求协作式取消；节点执行器在安全检查点确认后才进入 `cancelled`。相同终态命令重放 MUST 返回原结果，不得重复追加事件。可重试失败 MUST 记录固定错误码和尝试序号，且不得把不可重试输入错误重新排队。

#### Scenario: 取消运行中的 Workflow Run

- **WHEN** 主体取消包含运行中节点的 Workflow Run
- **THEN** 系统记录 `cancel_requested`，并通过 Node Executor Port 请求协作式取消
- **AND** 系统不强杀 Provider、不伪造节点已取消或新增第二次执行

#### Scenario: 节点受控失败并按策略重试

- **WHEN** 节点返回固定的可重试错误且尚未达到 Version 策略上限
- **THEN** Node Run 记录安全失败事实并进入受策略控制的后续尝试状态
- **AND** 原始异常、Prompt、凭据和 Provider 响应不进入事件或安全 View

#### Scenario: 不可重试输入失败

- **WHEN** 节点输入引用缺失、主体无权访问或能力契约校验失败
- **THEN** Node Run 和 Run 进入稳定失败状态，并保持节点 `attempt_count=0`
- **AND** 系统不调用 Node Executor，不创建后续执行尝试或 Task
- **AND** 使用相同命令标识重放时返回原失败结果，不重复追加事件
