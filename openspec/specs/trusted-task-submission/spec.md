# trusted-task-submission Specification

## Purpose
定义已认证服务端生产者提交 Task 的内部边界、固定任务策略、主体归属、安全输入约束以及与公开协议和后续 Worker 能力的隔离规则。

## Requirements

### Requirement: 已注册的服务端生产者必须以固定策略提交任务

系统 MUST 为已注册的服务端生产者提供受信任 Task 提交能力。每个提交能力 MUST 使用服务端固定的 task type、最大尝试次数和手动重试策略；调用方不得在提交命令中覆盖这些策略。成功提交 MUST 返回安全 Task 状态投影并沿用生命周期既有的创建幂等语义。

#### Scenario: 受信任生产者创建排队任务
- **WHEN** 已注册生产者以有效提交档案和有效提交命令提交任务
- **THEN** 系统使用档案固定的 task type、最大尝试次数和重试策略创建 `queued` Task
- **AND** 返回不含输入指纹或 lease 的安全 Task 状态投影

#### Scenario: 重放同一受信任提交
- **WHEN** 同一可信主体以相同提交档案、幂等键和输入指纹重复提交
- **THEN** 系统返回首次创建的稳定 Task 标识和当前状态
- **AND** 不创建第二个 Task 或第二条创建 Event

### Requirement: 受信任提交必须从已认证主体确定归属

系统 MUST 从已认证且具有非空 subject 的可信主体确定 Task owner。受信任提交命令不得包含可覆盖 owner 的字段；匿名、未认证或缺少 subject 的主体不得创建 Task。

#### Scenario: 已认证主体提交任务
- **WHEN** 已认证主体使用受信任提交能力提交有效命令
- **THEN** 创建的 Task owner 等于该主体的 subject
- **AND** 调用方不能通过命令指定其他 owner

#### Scenario: 未认证主体被拒绝
- **WHEN** 匿名、未认证或 subject 为空的主体尝试提交任务
- **THEN** 系统返回受控的可信主体错误
- **AND** 不创建 Task、Attempt、Event 或命令回执

### Requirement: 展示元数据必须受提交档案约束

系统 MUST 仅接受提交档案声明的展示元数据字段及字符串值。未知字段、空字段名或非字符串值 MUST 在写入 Task 前被拒绝；拒绝不得改变已有的同幂等键 Task。

#### Scenario: 提交允许的展示字段
- **WHEN** 提交命令只包含档案允许的非空字符串展示字段
- **THEN** 系统将该字段保存为 Task 的展示元数据
- **AND** 创建 Event 仍只包含生命周期规定的安全事件元数据

#### Scenario: 提交未知展示字段
- **WHEN** 提交命令包含提交档案未声明的展示字段
- **THEN** 系统拒绝提交并返回受控的策略错误
- **AND** 不创建或修改 Task 生命周期事实

### Requirement: 受信任提交能力不得形成公开创建协议

系统 MUST 将受信任 Task 提交保持为服务端内部 Application 能力。TM-03 不得新增浏览器、HTTP、MCP 或 Function Calling 的任务创建入口，也不得允许业务 Application 直接使用低层生命周期创建命令。

#### Scenario: 开发者检查协议与业务依赖边界
- **WHEN** 开发者检查本 Change 引入的接口路由和业务 Application 依赖
- **THEN** 系统不存在 Task 创建协议路由或公开创建 Schema
- **AND** 业务 Application 只能依赖受信任提交能力而不能导入低层创建命令或生命周期服务
