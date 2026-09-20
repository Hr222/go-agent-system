## MODIFIED Requirements

### Requirement: Worker 必须从受信任边界运行

系统 MUST 只允许由服务端 Composition Root 注册的 Worker 和执行器访问领取、续租及含 lease 的执行器契约。系统 MUST 提供独立于 HTTP 进程的受信任 Worker 运行入口，按受配置约束的周期运行既有恢复、重试和固定执行器领取；每个循环阶段完成后 MUST 关闭其 Session 与 Composition 资源。系统 MUST 不为这些契约新增浏览器、公开 HTTP、MCP 或 Function Calling 入口；安全 Task 投影和普通状态查询 MUST 不包含 lease。

#### Scenario: 未注册执行器不能领取任务

- **WHEN** Worker 使用未在服务端固定注册表中的 task type 请求执行
- **THEN** 系统不把任务交给未知执行器
- **AND** 返回不含 token、输入或完整异常的稳定错误，并保持任务事实一致

#### Scenario: 普通状态读取不暴露 lease

- **WHEN** 调用方读取已领取 Task 的安全状态
- **THEN** 返回状态和可展示字段
- **AND** 返回内容不包含 lease token、Attempt 内部字段或输入指纹

#### Scenario: 独立运行入口消费 Tender Task

- **WHEN** 运维显式启动受配置的 Tender Worker 运行入口，且存在可执行的 Tender Task
- **THEN** 入口通过服务端固定的 Tender Executor 运行既有恢复、重试和领取循环
- **AND** HTTP 进程、MCP 请求和浏览器不启动或选择 Worker

#### Scenario: 单轮完成后释放运行资源

- **WHEN** Worker 循环的恢复、重试或执行阶段完成或发生受控异常
- **THEN** 该阶段关闭自己的数据库 Session 与 Composition 资源
- **AND** 后续轮次可以独立继续，不复用失败阶段的持久化对象
