# Capability Attachment Resolution Specification

## Purpose

在能力执行之前，按能力声明受控地解析附件引用，校验主体、会话、媒体类型和大小，并将内容限制在服务端内部边界，避免客户端直接接触文件内容。

## Requirements

### Requirement: 能力级附件解析

系统 MUST 在能力执行前按能力声明校验附件引用的主体、会话、媒体类型、大小和数量，并通过服务端 Port 读取内容。

#### Scenario: 合法附件解析

- **WHEN** 请求包含属于当前主体且满足能力约束的附件引用
- **THEN** 系统生成服务端内部输入供能力 Adapter 使用
- **AND** 不把物理路径或完整内容返回给客户端

#### Scenario: 类型或大小不符

- **WHEN** 附件不满足能力声明的类型或大小限制
- **THEN** 系统返回输入校验失败
- **AND** 不创建或执行能力提议

#### Scenario: 引用伪造

- **WHEN** 客户端提交不存在、过期或其他主体的附件 ID
- **THEN** 系统拒绝解析
- **AND** 不调用 Agent Runtime
