## MODIFIED Requirements

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

系统 MUST 保持现有普通流式持久化语义：客户端取消、上游错误、空回答或 assistant 写入失败时不得追加 assistant Message；上下文快照接入不得改变既有 SSE 事件和安全错误映射。

#### Scenario: 第二轮流式生成中途失败

- **WHEN** 模型已返回部分文本后本轮流式请求失败或被取消
- **THEN** 系统按既有受控错误或取消语义结束
- **AND** Conversation 只新增本轮 user Message
- **AND** 不把部分回答作为历史 assistant Message 保存
