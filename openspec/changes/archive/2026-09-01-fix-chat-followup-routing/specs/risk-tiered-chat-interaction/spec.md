## MODIFIED Requirements

### Requirement: 服务端按风险策略决定 Chat 交互分支

系统 MUST 在 `POST /api/v1/interaction/chat/stream` 中先完成候选召回、结构化识别、可信主体权限过滤、目录读取和输入复核，再依据服务端目录的确认策略决定下一步。浏览器 MUST NOT 通过能力代码、确认策略、权限或分发键选择执行分支。对于非空输入，当识别结果为 `unrecognized` 时，系统 MUST 仅在当前主体可用的固定 `chat.general` 经服务端目录复核且确认策略为 `never` 后，将原始输入作为通用 Chat 继续处理。

#### Scenario: 普通对话无需批准并进入流式输出

- **WHEN** 用户消息被识别为当前主体可用的 `chat.general`，且目录策略为 `never`
- **THEN** 系统不创建确认提议、不调用确认接口
- **AND** 系统在复核目录、权限和输入后开始受控 Chat 流式输出

#### Scenario: 未识别的自然追问回退到通用 Chat

- **WHEN** 非空用户消息的结构化识别结果为 `unrecognized`
- **AND** 服务端目录将当前主体可用的固定 `chat.general` 复核为策略 `never` 的有效通用 Chat 能力
- **THEN** 系统 MUST 使用原始用户消息作为该能力输入并进入受控 Chat 流式输出
- **AND** 系统 MUST NOT 创建确认提议或执行其它能力

#### Scenario: 需要批准的能力仅返回批准事件

- **WHEN** 用户消息匹配当前主体可用且策略为 `always` 或 `conditional` 的能力
- **THEN** 系统创建主体绑定、短期一次性的确认提议并发送 `approval_required` 事件
- **AND** 系统不调用目标 Application Use Case、Agent Runtime 或外部能力

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
