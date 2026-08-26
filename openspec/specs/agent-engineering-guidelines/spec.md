# agent-engineering-guidelines Specification

## Purpose
TBD - created by archiving change refresh-agent-engineering-guidelines. Update Purpose after archive.
## Requirements
### Requirement: 协作规则必须明确项目事实来源

协作规则 MUST 区分用户指令、稳定架构、当前 Change、系统进度、运行说明和代码验证证据的职责。LLM 在信息冲突时 MUST 报告冲突并依据对应来源处理，不得把阶段进度写死为长期事实，也不得把设计描述直接当作已实现结果。

#### Scenario: 设计与实现存在差异

- **WHEN** `ARCHITECTURE.md` 的稳定设计与当前代码或测试结果不一致
- **THEN** LLM 明确指出设计与实现的差异
- **AND** 不未经指令修改架构基线或声称实现已经完成

### Requirement: 协作规则必须提供当前项目的最小认知模型

协作规则 MUST 将系统理解为 Agent 开发平台，并明确平台能力、业务应用和横向技术层。它 MUST 说明 `ingestion` 是通用资料处理 Pipeline，Knowledge/RAG 是独立平台能力，`online` 是业务应用，`agents/tender` 是业务 Agent，Agent Runtime 属于 Agent Management，Gateway 只处理自然语言控制面，Composition Root 只负责对象组装。

#### Scenario: LLM 判断模块归属

- **WHEN** 用户要求新增或调整资料处理、RAG、Online、Tender 或 Agent 调用相关内容
- **THEN** LLM 按平台能力与业务应用边界判断范围
- **AND** 不会把政策资料样本、Tender 或 Online 误判为平台一级能力
- **AND** 不会把 Gateway 误判为所有 HTTP 接口的必经层

### Requirement: 协作规则必须区分讨论和实施行为

LLM MUST 先识别用户请求属于讨论、评审、诊断或实施。用户未明确要求实施时，LLM MUST 保持只读，不修改代码、文档或 OpenSpec 文件；进入实施后 MUST 读取相关上下文、限定变更范围、完成验证并同步任务状态。

#### Scenario: 用户要求先讨论方案

- **WHEN** 用户要求解释、评审或讨论某个设计但没有要求执行
- **THEN** LLM 只读取和分析相关内容
- **AND** 不修改工作区文件

### Requirement: 开发规则必须要求适度的中文注释

开发规则 MUST 要求复杂函数、关键流程、跨模块协调、非直观业务规则、安全边界、兼容逻辑和重要取舍使用简洁中文注释或中文说明。对于可直接从代码理解的简单逻辑，规则 MUST 禁止通过逐行注释制造重复内容。

#### Scenario: 新增非直观业务逻辑

- **WHEN** 开发者新增一段涉及安全边界、失败处理或重要业务取舍的复杂逻辑
- **THEN** 代码包含说明行为和必要原因的中文注释
- **AND** 注释不泄露敏感数据，也不重复描述显而易见的代码

### Requirement: 交付规则必须包含验证和敏感数据检查

交付规则 MUST 要求根据变更范围执行相关测试、静态检查、构建、OpenSpec 校验和差异检查。提交前 MUST 检查工作区与暂存区，并阻止 `.tmp`、`.runtime`、`backups`、真实 SQL 备份、OCR 输出、`.env`、密钥和真实业务资料进入 Git。

#### Scenario: 工作区包含敏感或临时文件

- **WHEN** 提交前工作区存在备份、临时目录、OCR 输出或敏感配置
- **THEN** LLM 明确提醒这些文件不得提交
- **AND** 只显式暂存用户确认范围内的安全文件

### Requirement: Git 提交规则必须统一且可审计

Git 规则 MUST 要求提交标题使用 `分类（模块）：简洁的中文动作描述`，分类使用项目约定的中文分类，一次提交只包含一个相互关联的变更。提交前 MUST 检查 staged diff；远程推送 MUST 以用户明确指令为前提。实现型 OpenSpec Change SHOULD 在任务完成并归档后提交。

#### Scenario: 变更准备提交

- **WHEN** 实现和验证已经完成且用户要求提交
- **THEN** LLM 使用中文分类提交标题并检查暂存差异
- **AND** 不把无关或敏感文件混入提交
- **AND** 未收到推送指令时不执行远程推送
