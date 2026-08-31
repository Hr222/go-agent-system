## ADDED Requirements

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

当异步调用方在 Conversation 持久化短操作已经启动后取消请求时，系统 MUST 等待该同步操作完成提交或回滚及资源关闭，再向调用方保持原有取消语义。已启动的操作未收口前，系统 MUST NOT 释放覆盖该轮次的 Conversation 租约。取消、上游失败、空回答或 assistant 写入失败时，系统 MUST 继续遵守父规格中 user 保留且不写入部分 assistant 的规则。

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
