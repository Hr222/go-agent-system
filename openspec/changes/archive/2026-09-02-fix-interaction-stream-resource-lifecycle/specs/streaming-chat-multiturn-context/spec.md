## MODIFIED Requirements

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
