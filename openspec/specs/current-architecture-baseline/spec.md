# current-architecture-baseline Specification

## Purpose
TBD - created by archiving change consolidate-current-architecture-document. Update Purpose after archive.
## Requirements
### Requirement: 项目必须提供唯一的当前架构基线

项目 SHALL 将 `ARCHITECTURE.md` 作为后续 Change、设计和实现的唯一当前架构依据。该文档 MUST 包含后端平台分层、对话运行时、主体与会话边界、知识库与附件边界、前端工程分层以及前后端接口边界。

#### Scenario: 开发者开始新的架构相关 Change
- **WHEN** 开发者依据仓库文档确认模块职责或依赖方向
- **THEN** `ARCHITECTURE.md` MUST 提供完整的当前架构约束，而无需组合 V1、V2 或前端架构文档

### Requirement: 统一基线必须区分事实与演化边界

`ARCHITECTURE.md` SHALL 明确区分当前已实现能力、已确认但尚未实施的设计边界，以及明确不在当前范围的能力。尚未实现的主体隔离、认证、缓存、上下文压缩、SubAgent、Workflow、Task Management 和 Harness MUST 不得被描述为已实现。

#### Scenario: 开发者评估未来会话能力
- **WHEN** 开发者阅读统一架构基线以安排会话、身份或上下文相关 Change
- **THEN** 文档 MUST 能识别哪些契约和插口已存在，哪些行为仍需要独立 Change 实现

### Requirement: 已合并的旧架构文档必须删除

项目 MUST 删除已被 `ARCHITECTURE.md` 完整吸收的 `ARCHITECTURE_V1.md`、`ARCHITECTURE_V2.md` 和 `FRONTEND_ARCHITECTURE.md`。协作说明、OpenSpec 配置、当前阶段文档和未归档 Change MUST 不再将这些文件作为架构依据。

#### Scenario: 开发者确认架构入口
- **WHEN** 开发者在当前维护文档或未归档 Change 中查找架构依据
- **THEN** 其 MUST 只指向 `ARCHITECTURE.md`，且三份已合并的旧架构文档 MUST 不存在于工作树

