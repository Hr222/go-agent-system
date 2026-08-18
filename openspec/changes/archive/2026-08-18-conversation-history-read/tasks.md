## 1. 读取契约与应用用例

- [x] 1.1 在 `modules/conversation/ports` 定义历史页结果、读取 Port 和页大小常量；结果契约不依赖 SQLAlchemy、FastAPI 或具体数据库。
- [x] 1.2 实现 Conversation 历史读取应用服务，校验 UUID、`limit` 和 `after_sequence`，并区分空会话与不存在会话。

## 2. PostgreSQL 读取适配器

- [x] 2.1 新增只读 PostgreSQL Repository，复用 P0.1 ORM、P0.1 映射和 P0.2 会话不存在错误；返回 Conversation 与消息领域对象，不泄漏 ORM。
- [x] 2.2 实现按 `conversation_id`、`sequence ASC` 和 `after_sequence` 的 `limit + 1` 查询，正确计算 `has_more` 与下一游标；读取不得执行写操作或锁定会话。
- [x] 2.3 在 `app/composition/conversation.py` 提供历史读取 Repository 和应用服务的组装入口，并验证具体适配器仅在 Composition Root 实例化。

## 3. 历史读取行为验证

- [x] 3.1 新增应用服务单元测试，验证默认/边界页大小、游标校验、空历史和结果契约。
- [x] 3.2 新增 PostgreSQL 集成测试，验证会话元数据、消息顺序、角色/内容/UUID 恢复和不存在会话错误。
- [x] 3.3 新增分页测试，验证 `limit + 1`、`has_more`、下一游标、后续页无重复，以及追加消息后可从游标继续读取。

## 4. 边界与回归

- [x] 4.1 更新架构边界测试，验证 Conversation 读取应用/Port 不依赖基础设施、HTTP、LLM 或 Agent，且本 Change 不新增 Conversation HTTP 路由。
- [x] 4.2 运行 Conversation 读取、写入、存储和架构测试及目标代码 Ruff；所有新增测试必须通过。
- [x] 4.3 运行全量后端测试和现有 `/api/v1/llm/chat` 回归测试，确认 P0.1/P0.2 与 V1 行为不变。
