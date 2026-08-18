## 1. 领域模型与转换边界

- [x] 1.1 在 `modules/conversation/domain` 定义不依赖 SQLAlchemy 的 `Conversation`、`Message`、UUID 标识和消息角色值对象；有效角色、非空内容与正整数顺序号不变量必须有单元测试。
- [x] 1.2 在基础设施层实现 Conversation/Message 领域对象与 ORM 记录之间的转换边界；转换后 UUID、角色、内容、顺序号和时间字段必须保持一致。

## 2. PostgreSQL 与 ORM 映射

- [x] 2.1 新增 `sql/007_conversation_model_storage.sql`，创建 `conversation` 和 `conversation_message` 表、外键、角色/内容/顺序号检查约束、唯一顺序约束及历史读取索引；脚本不得创建 HTTP、LLM 或 Agent 相关对象。
- [x] 2.2 新增 SQLAlchemy Conversation/Message ORM 记录并注册到持久化模型包；`Base.metadata.create_all()` 必须能在隔离 PostgreSQL schema 中创建相同的表映射。

## 3. 存储完整性验证

- [x] 3.1 新增 PostgreSQL 集成测试，验证有效 Conversation/Message 可持久化和恢复，Message 不可引用不存在的 Conversation，并验证会话删除时不会留下孤立消息。
- [x] 3.2 新增约束测试，验证非法角色、空白内容、非正顺序号和同一会话内重复顺序号都会被拒绝，同时不同会话允许相同顺序号。
- [x] 3.3 新增或更新架构边界测试，验证 Conversation 领域模型不依赖 SQLAlchemy，且本 Change 没有新增 Conversation HTTP 路由、LLM 调用或 Agent 调用。

## 4. 回归验证

- [x] 4.1 运行 Conversation 领域与持久化测试、相关架构边界测试和 Ruff；所有新增测试必须通过。
- [x] 4.2 运行现有 LLM 单轮 Chat 回归测试，确认 `/api/v1/llm/chat` 的行为和契约未因模型存储引入而改变。
