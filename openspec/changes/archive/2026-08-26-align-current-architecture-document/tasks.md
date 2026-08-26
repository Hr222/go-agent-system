## 1. 建立文档依据与统一术语

- [x] 1.1 对照迁移后的目录、路由、Composition Root、Gateway、Agent 调用、Ingestion、Knowledge、Online 和 Tender 实现，形成可追溯的模块与图边核对清单。
- [x] 1.2 对照 `streaming-chat-multiturn-context` 的已确认设计，确认 History Read Service、Context Builder、`max_messages=20`、`max_cost=12_000` 与 `ChatLlmRequest.history_messages` 的固定表述。
- [x] 1.3 固定架构文档、系统看板与 OpenSpec 的职责边界，以及平台能力、业务应用和横向技术层的统一术语。

## 2. 重构 ARCHITECTURE.md

- [x] 2.1 重写文档定位、系统分层和目录导航，使其只呈现完整稳定的架构设计，不含交付进度、历史演化或未来路线图。
- [x] 2.2 重写平台与业务模块说明，准确界定 LLM、Knowledge/RAG、Ingestion、Conversation、Dialogue、Interaction、Agent Management、Attachment、Security、Online 与 Tender 的职责和依赖。
- [x] 2.3 更新总体架构图，区分直接 HTTP Application 路径、经 `InteractionChatStreamApplication` 和 Gateway 的 Chat 路径，以及仅负责组装的 Composition Root。
- [x] 2.4 更新 Agent Management 图，表达 Capability Catalog、确认与调用策略、`DialogueAgentInvocation`、`AgentCallDispatcher`、Agent Runtime、Tender 和 `DialogueAgentContinuation` 的受控顺序。
- [x] 2.5 更新 Ingestion/Knowledge 图，表达 Ingestion Pipeline 到 Knowledge 写入能力和 LLM Embedding Port 的关系，以及 Online 经 Knowledge Query/RAG 使用检索的边界。
- [x] 2.6 更新 Conversation/Dialogue 多轮上下文图，表达历史读取、连续近期窗口、成本预算、`history_messages` 与单次 `user_prompt` 的装配规则。

## 3. 重构 README

- [x] 3.1 更新项目背景、系统用途与既有能力说明，使其面向使用者而不重复详细架构设计。
- [x] 3.2 更新目录导航、环境要求、运行指令和接口访问章节；只有地址可确认时才写入具体服务地址。
- [x] 3.3 链接 `ARCHITECTURE.md` 作为唯一的详细架构说明，并检查 README 未保留重复的架构图、依赖图或业务流程图。

## 4. 验证与交付检查

- [x] 4.1 逐项审阅文字、目录和图边：直接 HTTP 不经 Gateway，Composition Root 不承担转发，`online -> LLM` 与 `Tender -> Knowledge` 不得出现，Tender 不是平台能力。
- [x] 4.2 逐项审阅上下文图：历史消息来自同一 Conversation、保持角色和顺序，当前输入只发送一次，且未引入未确认的上下文机制。
- [x] 4.3 检查 Markdown 链接、标题层级、目录路径和接口访问说明；运行适用的架构边界测试、`openspec validate "align-current-architecture-document" --strict` 与 `git diff --check`。
- [x] 4.4 完成人工审阅，确认 `ARCHITECTURE.md`、README、系统看板和 OpenSpec 没有职责重叠后，再标记 Change 完成。
