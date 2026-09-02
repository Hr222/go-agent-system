# streaming-chat-multiturn-context Specification

## Purpose

Define how ordinary streaming Chat uses recent history from the current
Conversation while preserving existing persistence and streaming failure
semantics.
## Requirements
### Requirement: 普通流式 Chat 使用同一会话的最近历史

系统 MUST 复用既有 Conversation 轮次租约执行普通流式 Chat：在租约内写入本轮 user Message，并以该消息的 `sequence` 建立同一 Conversation 的有界历史读取边界，再通过现有上下文策略选择最近连续消息窗口。模型请求 MUST 使用该边界内的历史角色和顺序；顺序号晚于本轮 user Message 的消息 MUST 不进入本轮请求；当前 user Message MUST 只作为当前输入发送一次。sequence 边界不得替代既有租约，也不得改变同一会话轮次串行化语义。

#### Scenario: 已有会话进行第二轮对话

- **WHEN** 主体对已包含首轮 user/assistant Message 的准入 Conversation 发起第二次普通流式 Chat
- **THEN** 模型请求包含本轮 user Message 之前、属于同一 Conversation 的最近历史
- **AND** 历史消息保留原始角色和顺序
- **AND** 本轮 user Message 作为 `user_prompt` 只出现一次
- **AND** 流式响应和 assistant Message 持久化行为保持既有契约

#### Scenario: 新会话进行首轮对话

- **WHEN** 可信主体在没有 `conversation_id` 时发起普通流式 Chat
- **THEN** 系统创建 Conversation 并保存本轮 user Message
- **AND** 模型请求不包含其他 Conversation 的历史
- **AND** 请求成功后保存本轮 assistant Message

#### Scenario: 同一会话请求等待既有轮次租约

- **WHEN** 同一 Conversation 的请求 A 正在执行普通流式 Chat，请求 B 同时发起
- **THEN** 请求 B 在 A 释放既有轮次租约前不得写入 user Message、读取模型上下文或调用 Provider
- **AND** A 的上下文读取使用 A 的 user `sequence` 作为包含边界
- **AND** A 成功收口后 B 才写入自己的 user Message，并可读取 A 已完整持久化的 assistant Message

### Requirement: 历史上下文受窗口和成本预算约束

系统 MUST 在本轮 user Message 的 sequence 截止的有界读取结果内，使用既有 Context Builder 的消息数量上限和成本预算选择历史。系统 MUST 保留最新的连续消息后缀并按 sequence 升序传给模型；不得跳过无法容纳的较早消息再选择更早消息，也不得静默截断任何消息内容。

#### Scenario: 历史超过消息窗口

- **WHEN** 当前 Conversation 的持久化历史超过上下文消息数量上限
- **THEN** 模型请求只包含本轮 user Message 之前允许范围内的最新连续消息
- **AND** 读取不需要从第一页扫描或加载完整历史
- **AND** 更早消息仍保留在 Conversation 历史中

#### Scenario: 当前用户消息超出预算

- **WHEN** 本轮 user Message 的成本单独超过上下文预算
- **THEN** 系统返回受控的上下文预算不足失败
- **AND** 已写入的 user Message 保留
- **AND** 不调用 Provider 或写入 assistant Message

### Requirement: 历史上下文必须绑定当前会话

系统 MUST 只读取并使用当前可信主体已准入 Conversation 的消息，并将读取范围限制在本轮 user Message 的 sequence 之内。普通流式 Chat MUST 在既有 Conversation 轮次租约内完成该事实写入、读取和 Provider 调用。跨会话、越权、读取边界失效或历史读取失败时，系统 MUST 拒绝构建模型请求，不得将其他会话或本轮之后的消息发送给 Provider。

#### Scenario: 请求携带其他主体的会话标识

- **WHEN** 主体使用不属于自己的 `conversation_id` 发起普通流式 Chat
- **THEN** 系统返回既有会话访问拒绝语义
- **AND** 不读取该会话历史、不调用 Provider 且不写入消息

#### Scenario: 历史读取在 user 写入后失败

- **WHEN** 当前 user Message 已成功写入但最近消息快照读取或上下文构建失败
- **THEN** 系统返回受控失败
- **AND** 当前 user Message 保留
- **AND** 不写入 assistant Message

#### Scenario: 读取边界不包含后续消息

- **WHEN** 当前 user Message 的 sequence 为 3，最近消息读取结果所在 Conversation 已存在顺序号为 4 的消息
- **THEN** 本轮模型请求不包含该更大顺序号的消息
- **AND** 本轮仍以当前 user Message 作为上下文候选末尾
- **AND** 普通流式 Chat 的正常同会话后续写入由既有轮次租约阻止在当前轮次内发生

### Requirement: 流式失败不得产生虚构的助手历史

系统 MUST 保持现有普通流式持久化语义：客户端取消、上游错误、空回答或 assistant 写入失败时不得追加 assistant Message；上下文接入不得改变既有 SSE 事件和安全错误映射。

#### Scenario: 第二轮流式生成中途失败

- **WHEN** 模型已返回部分文本后本轮流式请求失败或被取消
- **THEN** 系统按既有受控错误或取消语义结束
- **AND** Conversation 只新增本轮 user Message
- **AND** 不把部分回答作为历史 assistant Message 保存

### Requirement: 普通流式对话的持久化操作不得阻塞异步事件循环

普通流式 Chat 在异步 Dialogue 入口中执行 Conversation 创建、解析、user Message 写入、上下文最近消息读取和 assistant Message 写入时，MUST 通过可等待的持久化执行边界调用同步 Conversation 能力。同步 SQLAlchemy 操作 MUST NOT 直接在事件循环中执行。该边界 MUST 保持父规格定义的主体访问、轮次租约、sequence 截止、上下文预算和消息失败语义。

#### Scenario: 阻塞的持久化操作不阻塞其他异步任务

- **WHEN** 一个流式 Conversation 持久化操作在同步 Worker 中被人为阻塞
- **THEN** 事件循环仍能执行心跳或其他不相关的异步任务
- **AND** Worker 完成后原持久化操作返回其领域结果或原有受控错误
- **AND** 系统不通过丢弃持久化操作或提前释放轮次租约来获得表面上的响应

#### Scenario: 不同会话在持久化等待期间仍可推进

- **WHEN** Conversation A 的短持久化操作正在等待数据库 Worker
- **AND** Conversation B 发起普通流式 Chat
- **THEN** B 可以执行自己的会话访问、上下文准备或 Provider 调用
- **AND** A 的持久化等待不得独占整个异步事件循环

### Requirement: 普通流式对话不跨模型生成持有 Conversation Session

每一次 Conversation 持久化短操作 MUST 创建并使用独立 Session，并在成功提交或失败回滚后关闭。Provider 流式生成期间 MUST NOT 持有用于 Conversation Access、消息写入或上下文读取的 Session 或数据库连接。assistant Message MUST 在完整非空回答形成后通过新的短持久化操作写入，完成事件的既有顺序 MUST 保持不变。

#### Scenario: 模型流期间已释放前置 Session

- **WHEN** 系统已经提交本轮 user Message 和上下文读取结果并开始 Provider 流
- **THEN** user 写入和上下文读取使用的 Session 均已关闭
- **AND** Provider 流期间没有 Conversation 持久化 Session 或连接被该轮次占用
- **AND** 完整回答形成后系统才创建用于 assistant 写入的新 Session

#### Scenario: 每个短操作独立收口

- **WHEN** 会话访问、user 写入、上下文读取或 assistant 写入中的任一短操作成功或失败
- **THEN** 对应 Worker MUST 完成提交或回滚
- **AND** 对应 Session MUST 被关闭
- **AND** 后续短操作不得复用已经关闭、发生异常或属于其他请求的 Session

### Requirement: 异步取消不得遗留持久化 Worker 或破坏轮次事实
当异步调用方在 Conversation 持久化短操作已经启动后取消请求时，系统 MUST 等待该同步操作完成提交或回滚及资源关闭，再向调用方保持原有取消语义。已启动的操作未收口前，系统 MUST NOT 释放覆盖该轮次的 Conversation 租约。取消、上游失败、空回答或 assistant 写入失败时，系统 MUST 继续遵守父规格中 user 保留且不写入部分 assistant 的规则。即使在收口等待期间再次收到取消，系统 MUST 继续等待同一 Worker Task 完成并消费其终态，不能让 Worker 在后台脱离监督。

#### Scenario: user 写入期间取消
- **WHEN** 请求在 user Message 持久化 Worker 已启动后被取消
- **THEN** Worker 完成事务收口并关闭 Session
- **AND** 系统随后向请求方报告取消
- **AND** 已提交的 user Message 保留，未提交的写入不留下部分事实
- **AND** Conversation 轮次租约不会早于该 Worker 收口释放

#### Scenario: assistant 写入期间取消或失败
- **WHEN** 完整回答已经形成但 assistant Message 的持久化操作被取消或失败
- **THEN** Session 和 Worker 均被收口
- **AND** 系统不发送表示 assistant 已成功持久化的完成事实
- **AND** 父规格定义的已有 user Message、错误映射和后续轮次可继续语义保持不变

#### Scenario: 持久化收口期间再次取消
- **WHEN** 请求第一次取消后系统正在等待持久化 Worker 收口，且调用方再次取消该等待任务
- **THEN** 系统继续等待 Worker 完成提交或回滚并关闭 Session
- **AND** 系统消费 Worker 的成功或失败终态后才重新抛出原始取消
- **AND** Conversation 轮次租约在 Session 关闭之后才释放
