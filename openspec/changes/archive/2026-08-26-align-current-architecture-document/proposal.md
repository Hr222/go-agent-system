## Why

代码已完成平台与业务模块的物理分层，但 `ARCHITECTURE.md` 和 README 仍混合了架构、进度、历史表述与过时调用关系。它们需要回到各自明确的职责：架构文档描述一份完整、稳定的系统设计，README 说明项目如何使用，而实际进度和交付过程分别由系统看板与 OpenSpec 管理。

## What Changes

- 重构 `ARCHITECTURE.md`，将其定位为当前系统的完整架构设计快照，不记录交付进度、历史演化或未来路线图。
- 以平台能力层、业务应用层和横向技术层重新组织系统定位、物理目录和模块职责；LLM、Knowledge/RAG、Ingestion、Conversation、Dialogue、Interaction、Agent Management、Attachment 与 Security 均属于平台能力。
- 明确两种入口：直接 HTTP Application 能力入口，以及经 Gateway 进行自然语言能力识别、确认和受控分发的 Chat 入口；Composition Root 只负责对象组装，不参与运行时请求转发。
- 准确表达 Agent Management 的能力目录、调用策略、`AgentCallDispatcher` 和 Agent Runtime；`online` 与 `agents/tender` 是业务实现，Tender 不是平台一级能力。
- 将 Ingestion 写为可复用的资料处理 Pipeline，政策知识库仅是验证样本；修正 Online、Knowledge/RAG、LLM 和 Tender 的依赖关系。
- 按 `streaming-chat-multiturn-context` 已确认的完成态，补充会话历史、Context Builder 和 LLM 请求历史的多轮上下文链路。
- 重构 README，仅保留项目背景、系统用途、既有能力、目录导航、运行方式、环境要求、接口访问说明和到架构文档的链接，不复制详细架构图与调用关系。

## Capabilities

### New Capabilities

- `current-architecture-documentation`：定义系统架构文档与 README 的职责边界、内容准确性和可验证的呈现要求。

### Modified Capabilities

无。本 Change 不改变运行时行为、HTTP/MCP/Function Calling 契约、持久化语义或安全策略。

## Impact

- 修改 `ARCHITECTURE.md`、README 及本 Change 的规划产物；不修改系统看板。
- 文档中的目录、模块职责和运行时调用方向以已批准的代码分层设计及关联 Change 的确认设计为准。
- 不修改应用代码、前后端行为、数据库 Schema、外部 Provider 或部署配置。
