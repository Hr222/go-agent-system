## ADDED Requirements

### Requirement: 既有流式 Conversation Runtime 从会话历史构建模型上下文

系统 MUST 扩展已完成的流式 Conversation Runtime，而不是新增平行的流式会话运行时。扩展后的同一运行时 MUST 为已准入 Conversation 的普通文本轮次先追加有效 user Message，再分页读取该会话历史并通过现有 ContextPolicy、ContextBudget 和 ContextBuilder 构建 ModelContext。系统 MUST 把当前 user Message 仅作为流式 LLM 的当前输入一次传入。

#### Scenario: 已有会话开始流式对话

- **WHEN** 已准入 Conversation 有有序历史且提交有效用户文本
- **THEN** 系统写入本轮 user Message 并以最新连续上下文窗口调用流式 LLM
- **AND** LLM 历史消息保留原始角色和顺序

#### Scenario: 上下文扩展复用既有消息事实链路

- **WHEN** 系统为普通文本轮次启用流式上下文
- **THEN** 会话创建或解析、Access 校验、user/assistant Message 写入及失败闭合继续由同一流式 Conversation Runtime 负责
- **AND** 系统不为相同普通 Chat 轮次调用第二个流式会话运行时

#### Scenario: 当前消息超出上下文预算

- **WHEN** 写入 user Message 后其自身无法容纳于 Context Budget
- **THEN** 系统报告受控预算错误
- **AND** 系统不调用流式 LLM 或写入 assistant Message

### Requirement: 流式回答只在完整成功后成为会话事实

系统 MUST 只在流式 LLM 正常完成且拼接回答非空时追加完整 assistant Message。流中断、取消、上游错误、空回答或 assistant 写入失败 MUST 不追加部分或虚构 assistant Message。

#### Scenario: 正常完成

- **WHEN** 流式 LLM 返回非空回答并正常结束
- **THEN** 系统追加一条完整 assistant Message
- **AND** 该 Message 的顺序号大于本轮 user Message

#### Scenario: 部分输出后失败

- **WHEN** 流式 LLM 返回部分文本后发生错误或被取消
- **THEN** 系统报告受控失败或取消
- **AND** Conversation 只保留本轮 user Message
