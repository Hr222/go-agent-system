## 1. 上下文契约与预算端口

- [x] 1.1 在 `modules/conversation/domain` 定义 `ModelContext`、上下文消息、`ContextPolicy` 和 `ContextBudget`；完成条件：领域对象保留来源消息标识、角色、内容、顺序与成本结果，并拒绝无效上限。
- [x] 1.2 在 `modules/conversation/ports` 定义消息成本计量 Port；完成条件：Conversation 模块可依赖该协议而不导入 LLM SDK、HTTP 或基础设施实现。

## 2. 上下文构建应用服务

- [x] 2.1 实现确定性的字符消息成本计量和 `ConversationContextBuilder`；完成条件：服务从同一会话的有序消息窗口按最新优先选择连续后缀，并以正序返回模型中立上下文。
- [x] 2.2 实现预算不足、输入会话不一致、顺序不严格递增和非法计量结果的显式错误；完成条件：服务不截断、重排、跳过中间消息或静默忽略异常输入。

## 3. 组装与模块公开边界

- [x] 3.1 在 `app/composition/conversation.py` 提供默认上下文构建服务组装入口，并公开必要的 Conversation 应用与领域契约；完成条件：具体默认计量器仅在 Conversation 应用/Composition 边界实例化。
- [x] 3.2 更新架构边界测试；完成条件：上下文构建领域、应用和 Port 不依赖基础设施、HTTP、LLM 或 Agent，且本 Change 不新增 Conversation HTTP 路由。

## 4. 行为验证与回归

- [x] 4.1 新增上下文构建单元测试；完成条件：覆盖空窗口、保留来源字段、数量策略、成本预算、最新消息超预算、连续后缀与正序输出。
- [x] 4.2 新增无效输入与可替换计量器测试；完成条件：覆盖无效策略/预算、跨会话、乱序、非法成本和自定义计量器。
- [x] 4.3 运行 OpenSpec 严格校验、Conversation 目标测试、架构测试、目标 Ruff、全量后端测试及 `/api/v1/llm/chat` 回归；完成条件：新增能力通过且 P0.1 至 P0.3 与 V1 行为不变。
