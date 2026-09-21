## Purpose

为 Workflow Run、Node Run 及其受控执行边界提供稳定的后端契约，作为后续调度、公开入口和多 Agent 能力的实现基础。

## Requirements

### Requirement: Workflow Version 必须是服务端校验的不可变能力图

系统 MUST 以服务端固定注册的 Workflow Version 描述有限有向无环图。每个节点 MUST 使用唯一节点标识、受支持的节点类型和固定 `capability_code`；每条边 MUST 引用同一 Version 中存在的节点。Version 注册或加载时 MUST 校验节点唯一性、边引用、无环性、能力目录绑定和输入/输出引用约束；运行期间不得原地修改已使用的 Version。

#### Scenario: 注册合法的固定能力 Workflow Version

- **WHEN** Composition Root 加载包含合法节点、边和已登记能力的 Workflow Version
- **THEN** 系统接受该 Version 并为后续 Run 提供稳定版本标识
- **AND** 节点执行目标来自服务端能力目录，不包含 URL、Python 类名或客户端分发键

#### Scenario: 拒绝无效或循环 Workflow Version

- **WHEN** Version 包含重复节点标识、未知节点引用、循环边、未登记能力或不符合输入契约的绑定
- **THEN** 系统拒绝加载该 Version 并返回稳定配置错误
- **AND** 不创建 Workflow Run、Task 或执行器实例

### Requirement: Workflow Run 创建必须主体绑定且幂等

系统 MUST 只允许受信任 Application/Port 以可信主体、固定 Workflow Version、标准化输入和幂等键创建 Workflow Run。相同主体、Version 和幂等键重复创建 MUST 返回原 Run；相同幂等键使用不同输入指纹 MUST 返回稳定冲突。普通浏览器、公开 HTTP、MCP 或 Function Calling 不得直接创建任意 Workflow Run。

#### Scenario: 创建新的 Workflow Run

- **WHEN** 受信任服务端以当前主体提交已启用 Version 和合法输入
- **THEN** 系统创建一个 `queued` Run 及其节点快照，并返回不含原始输入的安全 Run View
- **AND** Run 记录固定 Version、owner、输入指纹和服务端生成的关联标识

#### Scenario: 重放相同创建命令

- **WHEN** 同一主体使用相同 Version、幂等键和输入指纹重复提交
- **THEN** 系统返回原 Run 和同一关联标识
- **AND** 不创建第二个 Run、Node Run 或初始事件

#### Scenario: 不同主体访问或冲突重放

- **WHEN** 另一主体读取、取消或重放该 Run，或同一幂等键提交不同输入指纹
- **THEN** 系统返回主体隔离错误或稳定幂等冲突
- **AND** 原 Run、节点状态和事件保持不变

### Requirement: Run 与 Node Run 必须使用受控状态和依赖语义

系统 MUST 为 Run 和 Node Run 定义稳定状态、尝试序号和有序安全事件。Run 至少支持 `queued`、`running`、`accepted`、`succeeded`、`failed`、`cancel_requested` 和 `cancelled`；Node Run 支持上述执行状态以及 `skipped`。节点只有在所有前置节点成功且输入引用可用时才可进入执行边界；节点适配器不得直接修改 Run、Node Run 或事件。

#### Scenario: 前置节点未完成时保持排队

- **WHEN** Workflow Run 中某节点仍有未成功的前置节点
- **THEN** 该节点保持 `queued` 或以安全查询结果标记为未就绪
- **AND** 系统不创建该节点的执行尝试或调用能力处理器

#### Scenario: 前置节点成功后节点可执行

- **WHEN** 某节点全部前置节点成功且边引用的安全输出可用
- **THEN** Application 将该节点交给受控 Node Executor Port
- **AND** 节点执行只能使用 Version 中固定的能力绑定和可信主体

#### Scenario: 异步节点被接收

- **WHEN** Node Executor 返回 `accepted` 和不透明 execution reference
- **THEN** Node Run 记录 `accepted` 状态与该引用，Workflow Run 不伪报为成功
- **AND** 事件不包含 lease、原始输入、Provider 响应或下载地址

### Requirement: Workflow 取消、失败和重试必须可控且幂等

系统 MUST 通过 Application 命令执行 Run/Node 的取消、失败和受策略约束的重试。运行中的 Run 取消只能先进入 `cancel_requested`，节点执行器在安全检查点确认后才进入 `cancelled`；相同终态命令重放 MUST 返回原结果，不得重复追加事件。可重试失败 MUST 记录固定错误码和尝试序号，且不得把不可重试输入错误重新排队。

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
- **THEN** Node Run 和 Run 进入稳定失败状态
- **AND** 系统不创建后续执行尝试或 Task

### Requirement: Workflow 公开投影必须隔离敏感执行事实

系统 MUST 只向受信任内部调用方返回包含 Run/Node 状态、版本标识、能力代码、白名单摘要、错误码和 execution reference 的安全 View。公开或普通状态读取 MUST 不包含原始输入、文件字节、lease token、内部 Attempt、Provider 原文、可执行地址或未审查的异常。

#### Scenario: 读取主体范围内的安全 Run View

- **WHEN** 当前主体读取自己拥有的 Workflow Run
- **THEN** 系统返回版本、状态、节点安全摘要和必要的关联引用
- **AND** 返回内容不泄露其他主体的 Run 或内部执行租约

#### Scenario: 读取其他主体的 Workflow Run

- **WHEN** 当前主体读取不属于自己的 Run 或 Node Run
- **THEN** 系统返回稳定的未找到或拒绝结果
- **AND** 不暴露该 Run 是否存在、输入内容或执行错误详情
