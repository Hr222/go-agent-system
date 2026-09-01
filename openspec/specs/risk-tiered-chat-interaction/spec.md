## Purpose

定义平台 Chat 的服务端意图分流、风险确认边界、SSE 事件契约，以及前端在同一对话消息流中展示普通回答和批准提议的行为。

## Requirements

### Requirement: 服务端按风险策略决定 Chat 交互分支

系统 MUST 在 `POST /api/v1/interaction/chat/stream` 中先完成候选召回、结构化识别、可信主体权限过滤、目录读取和输入复核，再依据服务端目录的确认策略决定下一步。浏览器 MUST NOT 通过能力代码、确认策略、权限或分发键选择执行分支。对于非空输入，当识别结果为 `unrecognized` 时，系统 MUST 仅在当前主体可用的固定 `chat.general` 经服务端目录复核且确认策略为 `never` 后，将原始输入作为通用 Chat 继续处理。

#### Scenario: 普通对话无需批准并进入流式输出

- **WHEN** 用户消息被识别为当前主体可用的 `chat.general`，且目录策略为 `never`
- **THEN** 系统不创建确认提议、不调用确认接口
- **AND** 系统在复核目录、权限和输入后开始受控 Chat 流式输出

#### Scenario: 需要批准的能力仅返回批准事件

- **WHEN** 用户消息匹配当前主体可用且策略为 `always` 或 `conditional` 的能力
- **THEN** 系统创建主体绑定、短期一次性的确认提议并发送 `approval_required` 事件
- **AND** 系统不调用目标 Application Use Case、Agent Runtime 或外部能力

#### Scenario: 未识别的自然追问回退到通用 Chat

- **WHEN** 非空用户消息的结构化识别结果为 `unrecognized`
- **AND** 服务端目录将当前主体可用的固定 `chat.general` 复核为策略 `never` 的有效通用 Chat 能力
- **THEN** 系统 MUST 使用原始用户消息作为该能力输入并进入受控 Chat 流式输出
- **AND** 系统 MUST NOT 创建确认提议或执行其它能力

#### Scenario: 识别为待澄清的业务请求不回退

- **WHEN** 识别结果为 `needs_clarification`
- **THEN** 系统发送受控 `result` 事件说明需要补充的资料
- **AND** 系统 MUST NOT 将该请求降级为 `chat.general`、创建确认提议或执行目标能力

#### Scenario: 无可用通用 Chat 时保留未识别结果

- **WHEN** 识别结果为 `unrecognized`
- **AND** 固定 `chat.general` 对当前主体不可用、目录复核失败或确认策略不是 `never`
- **THEN** 系统发送受控 `result` 事件说明下一步或失败原因
- **AND** 系统不创建确认提议且不执行目标能力

#### Scenario: 拒绝或失败结果保持受控返回

- **WHEN** 识别结果为拒绝或失败
- **THEN** 系统发送受控 `result` 事件说明下一步或失败原因
- **AND** 系统不创建确认提议且不执行目标能力

### Requirement: 交互流提供稳定且受控的事件契约

系统 MUST 通过 `text/event-stream` 返回交互流。普通 Chat 输出使用既有 `meta`、`delta` 和 `complete` 事件；批准分支使用 `approval_required`；非流式路由结果使用 `result`。`approval_required` 和 `result` 数据 MUST 只包含可安全展示的交互状态，不得包含分发键、完整输入、权限、执行器或 Provider 对象。

#### Scenario: 普通 Chat 正常完成

- **WHEN** 低风险普通 Chat 成功开始并完成输出
- **THEN** 系统先发送包含请求标识、模型标识和提示版本的 `meta` 事件
- **AND** 系统按模型生成顺序发送一个或多个 `delta` 事件，并以 `complete` 事件结束

#### Scenario: 批准事件不泄漏内部执行信息

- **WHEN** 系统发送 `approval_required` 事件
- **THEN** 事件仅包含提议标识、用户可读摘要、确认提示和受控状态
- **AND** 事件不包含能力分发键、提议完整输入或权限集合

#### Scenario: 流在输出开始后发生错误

- **WHEN** 普通 Chat 已发送流式事件后发生 Provider 或执行错误
- **THEN** 系统发送一个包含稳定错误码和可展示信息的 `error` 事件并关闭流
- **AND** 系统不发送 `complete` 事件且释放本次流资源

#### Scenario: 用户取消交互流

- **WHEN** 浏览器中止正在进行的交互流请求
- **THEN** 系统停止消费后续模型输出并释放流资源
- **AND** 系统不将该取消记录为目标能力执行失败

### Requirement: Chat 页面以受控事件恢复真实逐增量展示

Chat 页面 MUST 使用交互流作为用户消息的唯一服务端路由入口。页面收到 `delta` 后 MUST 按接收顺序加入渲染队列，以用户可感知的节奏逐步展示；页面不得在接收完整答案后伪造逐字动画。页面收到 `approval_required` 时 MUST 在同一消息流中展示批准卡，且批准前不得发起目标执行。

#### Scenario: 普通对话呈现逐增量回答

- **WHEN** Chat 页面收到普通对话的 `meta`、一个或多个 `delta` 和 `complete` 事件
- **THEN** 页面先显示连接中状态，随后显示输出中状态和逐步增加的回答文本
- **AND** 页面在待展示文本排空后才将该消息标记为已完成

#### Scenario: 页面收到批准事件

- **WHEN** Chat 页面收到 `approval_required` 事件
- **THEN** 页面显示用户可读的批准卡以及批准和取消操作
- **AND** 页面不显示内部能力代码、分发键或结构化输入

#### Scenario: 页面收到澄清或失败结果

- **WHEN** Chat 页面收到 `result` 或 `error` 事件
- **THEN** 页面在消息流中显示可理解的澄清、拒绝或失败状态
- **AND** 页面不自动重试或重复提交能力执行
