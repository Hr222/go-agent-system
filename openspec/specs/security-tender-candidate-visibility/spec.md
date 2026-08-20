## Purpose

Ensure Tender capability candidates and intent recognition remain scoped to the
request principal's permissions, including the static-principal HTTP mode.

## Requirements

### Requirement: 受权限控制的 Tender 候选识别

Interaction Gateway MUST 只向拥有 `agent:tender:execute` 的主体提供受保护 Tender 能力候选，并在执行前继续校验能力输入和确认策略。

#### Scenario: 静态授权主体识别 Tender
- **WHEN** static 主体拥有 `agent:tender:execute` 并提出生成投标骨架请求
- **THEN** Tender 可以进入候选范围
- **AND** 请求不会因为候选权限过滤而直接退回通用聊天

#### Scenario: 匿名主体不可发现 Tender
- **WHEN** 匿名主体提出同一请求
- **THEN** Tender 不进入可用候选范围
- **AND** 不产生 Tender Agent 执行

#### Scenario: 缺少文件输入
- **WHEN** 已授权主体识别出 Tender 但未提供必需文件输入
- **THEN** 系统返回明确澄清
- **AND** 不创建可执行确认或调用 Tender Runtime
