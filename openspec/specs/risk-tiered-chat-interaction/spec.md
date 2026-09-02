## Purpose

定义平台 Chat 的服务端意图分流、风险确认边界、SSE 事件契约，以及前端在同一对话消息流中展示普通回答和批准提议的行为。
## Requirements
### Requirement: 服务端按风险策略决定 Chat 交互分支

系统 MUST 在 `POST /api/v1/interaction/chat/stream` 中先完成候选召回、结构化识别、可信主体权限过滤、目录读取和输入复核，再依据服务端目录的确认策略决定下一步。浏览器 MUST NOT 通过能力代码、确认策略、权限或分发键选择执行分支。对于非空输入，当识别结果为 `unrecognized` 时，系统 MUST 仅在当前主体可用的固定 `chat.general` 经服务端目录复核且确认策略为 `never` 后，将原始输入作为通用 Chat 继续处理。上述同步准备操作 MUST 不直接占用异步事件循环；准备完成后使用的流式执行不得依赖准备阶段的请求级数据库 Session。

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

#### Scenario: 同步准备不阻塞其他异步任务
- **WHEN** 候选目录、Embedding 或结构化识别中的同步操作被人为阻塞
- **THEN** 事件循环仍能执行其他不相关的异步任务
- **AND** 准备操作完成后返回原有授权、澄清或失败结果

#### Scenario: SSE 开始后不再持有准备阶段 Session
- **WHEN** 交互准备成功并开始普通 Chat 的 Provider 流
- **THEN** 准备阶段使用的请求级数据库 Session 已完成关闭
- **AND** Provider 流期间不持有该 Session 或其他交互目录 Session

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
- **WHEN** 页面收到 `approval_required` 事件
- **THEN** 页面显示用户可读的批准卡以及批准和取消操作
- **AND** 页面不显示内部能力代码、分发键或结构化输入

#### Scenario: 页面收到澄清或失败结果
- **WHEN** 页面收到 `result` 或 `error` 事件
- **THEN** 页面在消息流中显示可理解的澄清、拒绝或失败状态
- **AND** 页面不自动重试或重复提交能力执行

### Requirement: 不同权限范围的候选索引刷新不得相互阻塞

系统 MUST 只对同一权限范围的候选索引刷新进行串行化；一个权限范围的目录读取或 Embedding 调用变慢时，其他权限范围 MUST 仍可开始或完成自己的索引刷新。

#### Scenario: 慢权限范围不阻塞其他范围

- **WHEN** 权限范围 A 的候选索引刷新正在等待 Embedding 返回
- **THEN** 权限范围 B 的候选索引刷新可以执行目录读取和 Embedding
- **AND** 同一权限范围 A 的第二次刷新仍等待第一次刷新完成

### Requirement: 普通交互接口的同步工作不得阻塞事件循环

系统 MUST 在异步 HTTP 路由执行同步的 Gateway 识别、候选目录读取、Embedding、结构化 LLM 或非 Agent 受控分发时，将该工作放入受保护的同步 Worker 边界。同步 Worker 完成前，路由不得提前释放其请求资源；Worker 完成后才返回既有受控响应。

#### Scenario: 意图识别上游阻塞时其他异步任务仍可运行

- **WHEN** `/api/v1/interaction/intent` 的目录、Embedding 或结构化识别调用被阻塞
- **THEN** 事件循环仍能执行其他不相关的异步任务
- **AND** 识别完成后返回既有的授权、待确认、澄清或失败响应

#### Scenario: 非 Agent 确认目标阻塞时其他异步任务仍可运行

- **WHEN** 非 Agent 提议确认触发 Chat、知识检索或策略复核且目标调用被阻塞
- **THEN** 事件循环仍能执行其他不相关的异步任务
- **AND** 目标完成后返回既有的完成、拒绝或失败响应

#### Scenario: 同步 Worker 被取消时资源先收口

- **WHEN** 调用方在同步 Worker 尚未完成时取消 HTTP 操作
- **THEN** 系统等待 Worker 完成并关闭其使用的资源
- **AND** 系统重新抛出原始取消，不把取消伪装成成功结果

### Requirement: 流式准备取消不得遗留不可操作的 Agent 提议

系统 MUST 在流式 Chat 准备阶段已建立 Agent 待确认状态但客户端在收到 `approval_required` 前断开时，消费该主体绑定的一次性提议和 pending invocation，并记录既有的 Agent 取消终态。系统 MUST NOT 调用 Agent Runtime、普通分发器或执行目标能力。

#### Scenario: 批准事件尚未发送时客户端断开

- **WHEN** Agent 准备已写入 `confirmation_required` 事实但 SSE 批准事件尚未发送，且调用方取消请求
- **THEN** 系统写入 `AGENT_CALL_CANCELLED` 终态并释放短期待确认状态
- **AND** Conversation Session 在取消事实提交或回滚后关闭

#### Scenario: 取消与确认并发竞争

- **WHEN** 客户端断开触发取消，同时另一个请求确认同一提议
- **THEN** 只有先原子消费提议的一方能够改变该提议状态
- **AND** 系统最多执行一次 Agent 调用且不会写入重复取消终态

#### Scenario: 准备未建立 Agent 状态时取消

- **WHEN** 普通 Chat、澄清、拒绝或准备失败结果在 SSE 开始前被取消
- **THEN** 系统不创建或取消 Agent 提议
- **AND** 系统关闭准备 Worker 资源并保留原始取消语义
