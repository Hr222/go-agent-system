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
