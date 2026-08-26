# module-layout-boundary Specification

## Purpose

Define the physical boundaries between reusable platform capabilities and
business-specific applications.

## Requirements

### Requirement: 平台能力与业务应用使用独立物理边界

系统 MUST 通过独立的 `platform` 和 `business` 包根目录表达平台能力与业务应用的物理归属。LLM、Knowledge/RAG、Ingestion、Context、Gateway、Capability Catalog、Agent Management、Dialogue、Attachment 和 Security MUST 属于平台层；`online` 和 Tender 等具体业务实现 MUST 属于业务层。

#### Scenario: 平台模块被业务应用使用

- **WHEN** 业务应用需要执行知识检索、模型调用或 Agent 受控运行
- **THEN** 业务应用可以依赖平台层公开的 Application/Port 契约
- **AND** 平台层不得导入具体业务应用包

#### Scenario: 旧的混合模块路径完成迁移

- **WHEN** 代码分层迁移完成
- **THEN** 旧的 `app/modules` 混合模块路径不再作为生产代码入口
- **AND** 代码库中不存在与新平台/业务包并行的第二套实现路径

### Requirement: 平台模块内部职责保持稳定

系统 MUST 在物理迁移后保持 `interaction` 内部 Platform Capability Catalog、Gateway、意图识别、确认和受控分发的现有职责边界；`conversation` 内部的会话、消息、事件、访问控制和上下文构建职责也 MUST 保持不变。此次迁移不得因目录调整引入新的并行能力目录或改变 Agent Runtime 的执行职责。

#### Scenario: 迁移后 Gateway 查询平台能力

- **WHEN** Gateway 为自然语言请求召回或复核候选能力
- **THEN** Gateway 继续通过现有能力目录契约读取 Agent 与非 Agent 能力
- **AND** 能力目录不执行任何业务 Use Case

#### Scenario: 迁移后 Agent Runtime 执行已授权 Agent

- **WHEN** Agent 调用已经通过目录、权限、输入和确认策略校验
- **THEN** Agent Runtime 使用固定受控映射执行 Agent
- **AND** Agent Management 不维护与 Platform Capability Catalog 并行的能力事实来源

### Requirement: 物理分层迁移保持外部契约行为不变

系统 MUST 在物理包迁移后保持现有 HTTP、MCP、Function Calling、数据库 Schema、Provider 适配和业务用例的外部行为不变。Composition Root MUST 继续负责具体适配器和固定分发绑定的组装。

#### Scenario: 迁移后调用现有 HTTP 接口

- **WHEN** 调用方使用已有 HTTP 路由和请求响应结构
- **THEN** 系统按照迁移前的业务语义处理请求
- **AND** 不要求调用方感知 Python 包路径变化

#### Scenario: 迁移后验证依赖边界

- **WHEN** 运行架构边界检查和测试
- **THEN** Interfaces 不直接依赖 Infrastructure，平台/业务模块不直接实例化具体适配器
- **AND** Composition Root 是具体适配器组装和分发绑定的唯一位置
