## MODIFIED Requirements

### Requirement: 统一基线必须区分事实与演化边界

`ARCHITECTURE.md` SHALL 明确区分当前已实现能力、已确认但尚未实施的设计边界，以及明确不在当前范围的能力。Task Management MUST 仅描述已实现的 `app/platform/task` 领域状态机、Attempt/Event 生命周期、命令幂等基础和仅供受信任执行器消费的 lease 契约；内存仓储仅可作为测试替身存在于测试范围。PostgreSQL 持久化、独立 Worker、HTTP 管理接口、业务接入、前端、E2E 与 Workflow 仍需后续独立 Change；尚未实现的真实认证、缓存、上下文压缩、SubAgent、Workflow 和 Harness MUST 不得被描述为已实现。

#### Scenario: 开发者评估未来会话能力
- **WHEN** 开发者阅读统一架构基线以安排会话、身份、Task Management 或上下文相关 Change
- **THEN** `ARCHITECTURE.md` MUST 区分 `app/platform/task` 已存在的领域契约、仅限测试的替身和仅限受信任执行器的 lease
- **AND** 开发者可以识别哪些契约和插口已存在，哪些持久化、Worker 和协议行为仍需要独立 Change 实现
