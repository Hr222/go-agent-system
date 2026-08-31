## ADDED Requirements

### Requirement: 同一进程内的普通流式 Chat 按 Conversation 互斥执行

系统 MUST 在单个后端进程中，以已创建或已准入 Conversation 的 `conversation_id` 隔离普通 `chat.general` 流式轮次。同一 Conversation 同时最多一轮可以执行；另一轮在当前轮结束前 MUST 不得写入 user Message、读取模型上下文或调用 Provider。不同 Conversation 的普通流式轮次 MUST 允许并行执行。系统 MUST NOT 将锁等待顺序作为严格 FIFO 或公开业务契约。

#### Scenario: 同一 Conversation 的后续请求等待当前轮结束

- **WHEN** 同一后端进程中，请求 A 已在 Conversation 内执行普通流式 Chat，请求 B 随后针对同一 Conversation 发起普通流式 Chat
- **THEN** 请求 B 在请求 A 结束前不写入本轮 user Message、不读取模型上下文且不调用 Provider
- **AND** 请求 A 正常完成后，请求 B 才可以开始本轮 user 写入和模型调用
- **AND** 请求 B 构建上下文时可以读取请求 A 已完整持久化的 assistant Message

#### Scenario: 不同 Conversation 仍可并行执行

- **WHEN** 同一后端进程同时对两个不同 Conversation 发起普通流式 Chat
- **THEN** 两个请求均可开始各自的普通流式模型调用
- **AND** 任一 Conversation 的长时间流式生成不得阻塞另一 Conversation 的轮次开始

### Requirement: 会话锁覆盖完整轮次并在所有终止路径释放

系统 MUST 在普通流式轮次写入 user Message之前取得对应 Conversation 的进程内锁，并持续持有至本轮完整 assistant 成功写入，或本轮因持久化失败、上下文失败、Provider 失败、超时、取消或消费者关闭而终止。系统 MUST 在每一种终止路径释放锁，使后续同会话请求可以继续。等待锁期间的取消 MUST 不新增 user 或 assistant Message。

#### Scenario: 当前轮 Provider 失败后释放会话锁

- **WHEN** 请求 A 已写入 user Message 并在普通流式 Provider 调用期间失败
- **THEN** 请求 A 不写入 assistant Message且保留已写入的 user Message
- **AND** 系统释放 Conversation 锁
- **AND** 等待同一 Conversation 的请求 B 可以随后开始

#### Scenario: 等待锁的请求被取消

- **WHEN** 请求 A 正在持有 Conversation 锁，请求 B 正在等待同一锁且其流请求被取消或关闭
- **THEN** 请求 B 不写入 user 或 assistant Message
- **AND** 请求 B 不保留会话锁引用
- **AND** 请求 A 结束后不会因请求 B 而继续执行额外的模型调用

#### Scenario: 流在首个事件前关闭时释放锁

- **WHEN** 普通流式 Runtime 已取得 Conversation 锁并返回流对象，但调用方在消费首个事件前关闭该流
- **THEN** 系统关闭底层流并释放 Conversation 锁
- **AND** 后续同 Conversation 请求可以获得锁并执行

### Requirement: 进程内锁状态按引用回收

系统 MUST 仅在当前进程内维护 Conversation 锁状态。一个 Conversation 没有持有者且没有等待者后，系统 MUST 回收其锁状态；系统 MUST NOT 因已结束的 Conversation 无界保留锁注册表条目。

#### Scenario: 最后一个轮次结束后回收锁状态

- **WHEN** 某 Conversation 的最后一个持有锁或等待锁的普通流式轮次结束
- **THEN** 系统移除该 Conversation 的进程内锁状态
- **AND** 后续对该 Conversation 的新普通流式轮次可以建立新的锁状态并正常执行

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

### Requirement: 已确认的对话 Agent 与普通流式 Chat 共享会话互斥边界

系统 MUST 在单个后端进程中，使同一 Conversation 的已确认对话 Agent 完整过程与普通 `chat.general` 流式轮次共享同一互斥边界。已确认 Agent 在取得该 Conversation 的轮次执行权后，系统 MUST 持续串行执行 Agent 调用、`agent_result` 或 `agent_error` 事实持久化、continuation 上下文构建、LLM 调用和 assistant Message 写入，直至该确认请求完成或失败。不同 Conversation 的已确认 Agent 与普通流式 Chat MUST 允许并行执行。

#### Scenario: 普通流式 Chat 等待同一 Conversation 的已确认 Agent

- **WHEN** 同一后端进程中，请求 A 已确认并开始执行 Conversation 内的对话 Agent，请求 B 随后针对同一 Conversation 发起普通 `chat.general` 流式 Chat
- **THEN** 请求 B 在 A 的 Agent 结果事实和 continuation assistant Message 到达终态前，不得写入本轮 user Message、读取模型上下文或调用 Provider
- **AND** A 成功完成后，B 才可以开始本轮 user 写入和模型调用
- **AND** B 构建上下文时可以读取 A 已完整持久化的 Agent 结果与 assistant Message

#### Scenario: 不同 Conversation 的轮次仍可并行执行

- **WHEN** 同一后端进程中，请求 A 已确认并执行 Conversation X 的对话 Agent，同时请求 B 对 Conversation Y 发起普通流式 Chat 或已确认的对话 Agent
- **THEN** 请求 B 可以在 A 完成前开始自身的模型或 Agent 调用
- **AND** Conversation X 的长时间执行不得阻塞 Conversation Y 的轮次开始

#### Scenario: Agent 或 continuation 失败后释放会话锁

- **WHEN** 已确认的对话 Agent 在执行、结果事实持久化或 continuation 期间返回失败
- **THEN** 系统保留该路径在失败前已持久化的 Conversation 事实，并保持既有受控失败响应
- **AND** 系统不得额外写入失败后未生成的 assistant Message
- **AND** 系统释放 Conversation 锁，使等待同一 Conversation 的后续普通 Chat 或已确认 Agent 可以执行

### Requirement: 等待会话锁的确认请求不消费一次性状态

系统 MUST 在 `confirm` 动作取得对应 Conversation 的会话锁后，才消费该动作的一次性确认 proposal 和 pending Agent invocation。等待锁的确认请求被取消时，系统 MUST 不消费 proposal 或 pending invocation，不启动 Agent，不调用 continuation LLM，且不写入新的 Conversation Message 或 Event。`cancel` 动作 MUST 保持既有确认取消语义，且不因本 Requirement 等待会话锁。

#### Scenario: 等待锁的确认请求被取消后可以重试

- **WHEN** 请求 A 正在持有某 Conversation 的会话锁，请求 B 对同一 Conversation 的待确认 Agent proposal 执行 `confirm` 并在等待期间被取消或断开
- **THEN** B 不消费该 proposal 或 pending invocation，不执行 Agent，且不写入新的 Conversation 事实
- **AND** A 结束后，该 proposal 的同一主体可以再次执行确认，并按既有一次性确认规则完成或被拒绝

#### Scenario: 同一 proposal 的并发确认只执行一次 Agent

- **WHEN** 同一主体并发提交同一待确认 Agent proposal 的两个 `confirm` 请求
- **THEN** 最多一个请求可以在取得会话锁后消费有效的一次性 proposal 和 pending invocation 并执行 Agent
- **AND** 另一个请求返回既有的受控 proposal 或调用上下文不可用结果
- **AND** 系统不得因此执行第二次 Agent 调用或重复写入 Agent 结果事实
