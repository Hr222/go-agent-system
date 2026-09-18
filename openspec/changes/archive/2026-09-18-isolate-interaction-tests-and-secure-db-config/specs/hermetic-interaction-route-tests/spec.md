## ADDED Requirements

### Requirement: Gateway 回退确认测试不依赖数据库
系统的确认接口回归测试 SHALL 为对话确认应用和 Gateway 提供稳定替身。在对话确认应用未处理提议时，测试 MUST 验证请求回退到 Gateway，且不要求可连接的本地 PostgreSQL 服务。

#### Scenario: 取消操作回退到 Gateway
- **WHEN** 对话确认替身返回未处理结果且客户端提交取消操作
- **THEN** 接口返回 Gateway 提供的 `cancelled` 结果
- **AND** 测试不构造真实数据库依赖

#### Scenario: 确认操作回退到 Gateway
- **WHEN** 对话确认替身返回未处理结果且客户端提交确认操作
- **THEN** 接口返回 Gateway 提供的失败或执行结果
- **AND** 测试不构造真实数据库依赖
