## ADDED Requirements

### Requirement: 已确认 Agent 的授权仍由 Interaction 控制面决定

系统 MUST 保持 Interaction/Gateway 对自然语言 Agent proposal 的消费、服务端能力目录复核、主体权限、输入契约和确认策略的控制权。Conversation turn 执行边界 MUST 在取得租约后调用该确认操作，并且只能将 Gateway 产生的批准分发信息交给 Agent 执行；不得以客户端提交的能力代码、分发键或输入直接启动 worker 或 Agent。

#### Scenario: 确认复核失败时不启动 Agent worker
- **WHEN** 已取得 Conversation 租约的确认请求在目录、权限、分发键或输入复核中被拒绝
- **THEN** 系统返回既有受控拒绝响应
- **AND** 系统不启动 Agent worker、不调用 Agent Runtime 且不写入新的 Agent 结果事实
- **AND** 系统按确认终态收口 matching pending invocation

#### Scenario: 已批准分发进入异步 Agent 轮次
- **WHEN** Interaction/Gateway 在 Conversation 租约内完成 proposal 消费并返回已批准的 Agent 分发信息
- **THEN** 系统只使用该批准信息启动对应的 Agent worker
- **AND** worker 执行继续遵守同 Conversation 互斥与不同 Conversation 可推进的要求

### Requirement: 已确认的对话 Agent 不得阻塞其他 Conversation 的轮次开始

系统 MUST 在单个后端进程中，使同一 Conversation 的已确认对话 Agent 与普通 `chat.general` 共享完整轮次互斥边界。Agent 轮次中的长时间同步 Agent 或最终回答工作 MUST 不阻塞不同 Conversation 的普通 Chat 或已确认 Agent 开始自身的模型或 Agent 调用。

#### Scenario: 同一 Conversation 的普通 Chat 等待已确认 Agent 终态
- **WHEN** 请求 A 已确认并开始执行 Conversation X 的对话 Agent，且其 Agent 或最终回答仍未完成
- **THEN** 请求 B 对 Conversation X 发起的普通流式 Chat 不写入 user Message、不读取上下文且不调用 Provider
- **AND** A 的 Agent result 或 error 事实及最终 assistant Message 到达终态后，B 才可以开始
- **AND** B 的上下文包含 A 已持久化的终态事实

#### Scenario: 不同 Conversation 在长 Agent 轮次期间推进
- **WHEN** 请求 A 正在执行 Conversation X 的长时间已确认对话 Agent
- **AND** 请求 B 对 Conversation Y 发起普通流式 Chat 或已确认对话 Agent
- **THEN** B 可以在 A 完成前开始自身的模型或 Agent 调用
- **AND** Conversation X 的执行不得因占用请求事件循环而阻塞 Conversation Y 的轮次开始

### Requirement: 已启动 Agent 轮次的取消不得破坏会话事实顺序

系统 MUST 区分等待轮次执行权与已启动执行的取消。等待同一 Conversation 租约的确认请求被取消时，系统 MUST 不消费 proposal 或 pending invocation，且该确认可以重试。已取得租约并开始执行的 Agent 轮次在客户端取消后，系统 MUST 保持该 Conversation 的互斥边界，直到 Agent 与 continuation 达到成功或受控失败终态。

#### Scenario: 等待租约时取消仍可确认
- **WHEN** 请求 A 持有 Conversation X 的轮次执行权，请求 B 正在等待确认 Conversation X 的 Agent
- **AND** B 在取得租约前被取消
- **THEN** B 不消费 proposal 或 pending invocation，不启动 Agent 且不写入新的 Conversation 事实
- **AND** A 结束后，同一主体可以使用该 proposal 再次确认

#### Scenario: 已启动 Agent 后客户端取消
- **WHEN** 已确认 Agent 已取得 Conversation X 的租约并开始执行，但客户端请求随后被取消
- **THEN** 后续对 Conversation X 的普通 Chat 或已确认 Agent 继续等待该轮次终态
- **AND** 系统不得在后台 Agent 或 continuation 仍可能写入事实时释放 Conversation X 的租约
- **AND** 该轮次终态后，等待的后续轮次可以继续执行

### Requirement: 一次性确认状态在确认轮次终态后收口

系统 MUST 在已取得 Conversation 租约后，对同一确认请求的 proposal 与 pending invocation 进行一致的终态收口。proposal 已被消费后，无论能力校验、pending 可用性、Agent 执行或 continuation 的结果为何，系统 MUST 不保留可再次进入确认执行路径的 matching pending invocation。

#### Scenario: proposal 消费后能力校验拒绝
- **WHEN** 已取得 Conversation 租约的确认请求消费 proposal 后发现能力不可用、目录不可用或输入不再有效
- **THEN** 系统返回既有受控拒绝响应且不执行 Agent
- **AND** 系统清理 matching pending invocation
- **AND** 对同一 proposal 的后续确认不会再次等待租约或执行 Agent

#### Scenario: Agent 或 continuation 失败后的确认状态
- **WHEN** 已确认 Agent 在执行、结果持久化或 continuation 期间达到受控失败终态
- **THEN** 系统保留既有已写入的 Conversation 事实并返回既有受控失败响应
- **AND** 系统清理 matching pending invocation
- **AND** 后续同一 Conversation 轮次可以在租约释放后继续
