## MODIFIED Requirements

### Requirement: 只有明确确认后才能受控分发

系统 MUST 仅在确认结果有效、目录条目启用、权限满足且输入完整时，通过固定分发键调用目标 Application Use Case。Chat 中已经识别为 Agent 的待确认提议 MUST 由 Gateway 在确认时只生成经过重新校验的 `ApprovedCapabilityDispatch`，再由 Dialogue Agent Invocation 调用 P2.6 Agent Dispatcher；Gateway 不得在该路径中直接执行 Agent Runtime。

#### Scenario: 用户确认 Chat 中的 Agent 能力

- **WHEN** 用户明确确认一个有效的 Tender Agent 提议，且该提议已绑定到对话调用上下文
- **THEN** Gateway 原子消费提议并返回服务端生成的 `ApprovedCapabilityDispatch`
- **AND** Dialogue Agent Invocation 调用对应 P2.6 Agent Runtime 用例

#### Scenario: 用户确认非 Agent 能力

- **WHEN** 用户明确确认一个有效的 RAG 问答或政策判断提议
- **THEN** Controlled Dispatcher 调用对应 Online Application 用例
- **AND** 系统不为了执行该能力启动 Agent Runtime

#### Scenario: 用户未确认或已取消

- **WHEN** 用户未确认、拒绝或取消待确认提议
- **THEN** 系统不调用任何目标能力
