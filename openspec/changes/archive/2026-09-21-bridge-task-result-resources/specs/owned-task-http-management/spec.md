## MODIFIED Requirements

### Requirement: HTTP 边界不得开放受信任执行契约

Task HTTP 接口 MUST 不提供任务创建、Worker 领取、lease 续租、结果回写或恢复调度入口。HTTP 路由 MUST 只能调用 Task Application/Port，不得直接访问 ORM、Session、Repository 或含 lease 的执行器契约；协议错误响应不得包含原始异常或敏感数据。系统可以提供 owner-scoped 成功 Task 结果资源读取和受控下载 URL 投影，但不得提供资源写入、物理路径或存储管理能力。

#### Scenario: 检查公开路由边界

- **WHEN** 外部调用者检查 Task HTTP 路由和响应 Schema
- **THEN** 只能发现主体隔离的查询、事件、取消、手动重试和成功 Task 的受控资源读取能力
- **AND** 不存在创建、领取、续租、结果回写、资源写入或 lease token 响应

#### Scenario: 底层异常被安全映射

- **WHEN** Task Application 或持久化适配器在 HTTP 请求期间失败
- **THEN** 系统返回固定错误代码和通用消息
- **AND** 响应、日志投影和事件中不包含 token、输入、Provider 凭据或完整异常
