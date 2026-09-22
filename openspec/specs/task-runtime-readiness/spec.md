# task-runtime-readiness Specification

## Purpose
TBD - created by archiving change harden-task-runtime-readiness. Update Purpose after archive.
## Requirements
### Requirement: 应用必须诊断 Task 数据库前置条件

应用启动阶段 MUST 检查 Task Management 运行所需的 `task`、`task_attempt`、`task_event` 和 `task_command_receipt` 表，并向日志暴露检查结果。

#### Scenario: Task 表结构完整
- **WHEN** 数据库连接可用且四张核心表均存在
- **THEN** 启动日志标记 Task schema 检查通过

#### Scenario: Task 表结构缺失
- **WHEN** 数据库连接可用但至少一张核心表不存在
- **THEN** 启动日志列出缺失表，并指引执行 `sql/013_task_lifecycle.sql`

#### Scenario: Task 数据库不可用
- **WHEN** schema 检查无法建立数据库连接或 Inspector 查询失败
- **THEN** 启动日志标记数据库不可用，且不尝试创建或修改任何表

### Requirement: Schema 检查不得改变任务 HTTP 契约

Task schema readiness 检查 MUST NOT 改变现有任务列表、详情、事件、取消和重试接口的路径、主体隔离或响应字段。

#### Scenario: 已认证主体访问任务接口
- **WHEN** Task schema 已就绪且主体访问自己拥有的任务
- **THEN** 接口继续按既有契约返回任务数据

#### Scenario: 未认证主体访问任务接口
- **WHEN** 主体未认证或主体标识无效
- **THEN** 接口继续返回现有的任务访问拒绝错误，不因启动诊断绕过权限边界
