## Why

`agent.md` 同时承担项目认知、人机协作、开发守则和 Git 交付约束，但其中仍保留旧的阶段目标、架构表述和 Agent 预留语义。`openspec/config.yaml` 也会向 LLM 注入过时的 `application/modules` 路径和模块边界，导致不同入口得到不一致的项目认知。

## What Changes

- 重写 `agent.md` 的文档职责、项目认知、开发流程、代码守则、测试验收和 Git 提交规则。
- 移除固定 Phase、未来路线和具体进度，改为要求 LLM 在工作开始时读取系统看板和当前 OpenSpec Change。
- 同步当前 `platform`、`business`、`interfaces`、`infrastructure`、`composition`、`shared` 分层，以及 Gateway、Agent Management、Ingestion、Knowledge/RAG、Online 和 Tender 的关键边界。
- 增加讨论、评审、诊断和实施请求的行为区分，明确未获实施指令时不得编辑文件。
- 增加中文注释规范：复杂逻辑、关键流程、非直观规则、兼容逻辑和重要取舍使用简洁中文注释；直白代码不添加逐行注释。
- 强化 OpenSpec 工作纪律、验证证据要求和敏感文件检查。
- 强化 Git 提交流程，要求中文分类提交标题、显式暂存、提交前检查，禁止将 `.tmp`、`.runtime`、`backups`、真实 SQL 备份、OCR 输出和敏感配置提交到 Git。
- 更新 `openspec/config.yaml` 的上下文与术语，使 OpenSpec 生成的规划产物也使用当前项目认知。

## Capabilities

### New Capabilities

- `agent-engineering-guidelines`：定义 LLM 项目认知、人机协作、中文注释、工程开发、验证和 Git 交付规则。

### Modified Capabilities

无。本 Change 不改变运行时能力、HTTP 契约、持久化语义或业务状态流转。

## Impact

- 修改 `agent.md`、`openspec/config.yaml` 以及本 Change 的规划产物。
- 不修改应用代码、前端行为、数据库 Schema、外部 Provider 或部署配置。
- 不改变系统架构；模块边界和依赖方向引用 `ARCHITECTURE.md`。
- 不引入运行时依赖，不产生数据迁移，也不涉及外部系统状态。
