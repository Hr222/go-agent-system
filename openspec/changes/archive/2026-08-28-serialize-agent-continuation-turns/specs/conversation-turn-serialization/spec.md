## ADDED Requirements

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
