# 低代码 Agent 平台 V1 学习资料

这组资料围绕 Go Agent System 的目标：构建一个允许用户创建 Agent、绑定工具和知识库、编排 Workflow，并运行多 Agent 协作流程的低代码平台。

## 资料入口

- [总学习清单](低代码%20Agent%20平台%20V1%20学习清单.md)：完整索引、概念检查、练习和 V1 验收主链路。
- [LLM 与 Prompt、上下文工程](LLM与Prompt上下文工程学习笔记.md)：模型、消息、上下文窗口、Token、结构化输出和流式调用。
- [Agent 与 Tool Calling](Agent与Tool%20Calling学习笔记.md)：Agent 组成、执行循环、工具授权、错误和安全边界。
- [LangChain 与 LangGraph](LangChain与LangGraph学习笔记.md)：框架概念、状态图和平台适配边界。
- [Workflow 与 Runtime](Workflow与运行时学习笔记.md)：Definition、Version、DAG、节点运行、调度、重试、取消和恢复。
- [多 Agent 协作](多%20Agent%20协作学习笔记.md)：Pipeline、Parallel、Fan-in、Supervisor、Handoff 和 Review。
- [平台数据模型与 Runtime](Agent平台数据模型与Runtime学习笔记.md)：Agent、Workflow、Task、Event、Artifact、版本和运行事实。
- [Builder、安全与评测](低代码平台Builder安全与评测学习笔记.md)：Agent Builder、Workflow Builder、权限、安全、观测和质量评测。

## 当前项目专题

本目录之外的专题资料仍然保留在 `docs/` 根目录，例如 RAG、上下文管理、Task Management、数据清洗和意图识别。它们是本组平台学习资料的基础专题，不移动、不重复维护。
