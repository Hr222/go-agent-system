## 1. LLM 历史消息契约

- [x] 1.1 扩展 `ChatLlmRequest`，定义模型中立的 `ChatLlmMessage` 与角色；完成条件：历史消息可按顺序携带 system/user/assistant 内容，默认空历史不影响现有单轮构造方式。
- [x] 1.2 更新 OpenAI-compatible 同步和流式 Chat 适配器；完成条件：Provider 按系统提示、历史角色消息、当前用户消息的顺序接收请求，且 assistant 角色映射正确。

## 2. 基础 Dialogue Runtime

- [x] 2.1 新增 `modules/dialogue` 的同步对话命令、结果契约与运行时；完成条件：运行时依赖 Conversation 应用服务、Context Builder 和 `ChatLlmPort`，返回持久化消息、模型元数据与 `ModelContext`。
- [x] 2.2 实现用户消息先写入、正向分页历史扫描、最近窗口保留、上下文构建、LLM 请求映射和助手消息写入；完成条件：当前用户消息只作为当前输入发送一次，历史按角色和顺序传递。
- [x] 2.3 实现空输入、空模型回答、上下文预算不足、LLM 失败和助手写入失败的显式行为；完成条件：失败后保留已成功写入的用户消息，不写入虚构 assistant 消息。

## 3. 组装与架构边界

- [x] 3.1 新增 `app/composition/dialogue.py` 组装入口；完成条件：使用外部注入的 Session 复用 Conversation 服务并注入既有 Chat LLM，Dialogue 模块不实例化具体适配器。
- [x] 3.2 更新架构边界测试；完成条件：Dialogue 仅依赖 Conversation/LLM 公开契约，不依赖 HTTP、SQLAlchemy、基础设施、Gateway、Agent 或 Task Management，且本 Change 不新增 Dialogue HTTP 路由。

## 4. 行为验证与回归

- [x] 4.1 新增 Dialogue Runtime 单元测试；完成条件：覆盖首轮和多轮成功路径、历史跨页、上下文结果、角色顺序、当前用户消息不重复和模型元数据返回。
- [x] 4.2 新增失败与组装测试；完成条件：覆盖空输入、空回答、预算不足、LLM/assistant 写入失败后的持久化边界，以及 Composition Root。
- [x] 4.3 扩展 Chat Provider 适配器测试；完成条件：覆盖含三种历史角色和无历史的同步/流式映射，确认 V1 单轮请求仍只产生两条 Provider 消息。
- [x] 4.4 运行 OpenSpec 严格校验、Dialogue/Conversation/LLM 目标测试、架构测试、目标 Ruff、全量后端测试及 `/api/v1/llm/chat` 回归；完成条件：新运行时通过且 V1 行为不变。
