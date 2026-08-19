## 1. Conversation 事件基础

- [x] 1.1 新增 `ConversationEvent` 领域模型、事件类型和读写 Port；完成条件：事件包含会话、调用、能力、顺序和 JSON 载荷不变量。
- [x] 1.2 新增 PostgreSQL ORM、映射和 `sql/008_conversation_event.sql`；完成条件：事件表可幂等创建，按会话/顺序/调用 ID 查询，不能保存空载荷或跨会话事件。

## 2. Dialogue Agent Invocation

- [x] 2.1 实现 Agent 结果白名单投影，支持普通 JSON 对象和 Tender 文件元数据；完成条件：原始 bytes、Provider 对象和异常堆栈不会进入事件。
- [x] 2.2 实现 `DialogueAgentInvocationService`；完成条件：校验/创建 Conversation，构造关联 ID，调用 P2.6 Dispatcher 一次，并写入成功/失败/待确认事件。
- [x] 2.3 在 Composition Root 组装事件 Repository、Invocation Service 和 Agent Runtime；完成条件：应用层只依赖 Conversation Port、Agent Dispatcher Port 和可信主体。

## 3. V2 HTTP 与前端感知

- [x] 3.1 新增 V2 Agent Invocation 请求/响应 Schema 与 HTTP 路由；完成条件：支持创建/复用会话，拒绝内部授权字段，返回会话 ID、调用 ID、状态和安全结果。
- [x] 3.2 更新交互页面和 API Client 展示确认、完成、失败及 Tender 文件元数据；完成条件：页面不显示分发键、权限集合或原始输入，旧 V1 页面流程保持可用。

## 4. 验证

- [x] 4.1 增加领域、Repository、Invocation、HTTP 和前端测试；完成条件：覆盖未授权不执行、成功持久化、失败脱敏、重复单次执行和伪造字段。
- [x] 4.2 运行后端全量 pytest、前端测试/TypeScript 构建、Ruff 和 OpenSpec 严格校验；完成条件：所有检查通过后再归档。
