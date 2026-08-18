## 1. 写入契约与应用用例

- [x] 1.1 在 `modules/conversation/ports` 定义 Conversation 写入 Port、创建/追加结果契约和会话不存在错误；契约不依赖 SQLAlchemy、FastAPI 或具体数据库。
- [x] 1.2 实现 Conversation 写入应用服务，提供创建会话和追加消息两个用例；服务先执行领域角色/内容校验，再将输入交给写入 Port 分配顺序并持久化。

## 2. PostgreSQL 写入适配器

- [x] 2.1 新增 Conversation PostgreSQL Repository，复用 P0.1 ORM 与映射；创建会话必须提交并返回领域对象，追加消息必须在失败时回滚。
- [x] 2.2 实现会话行锁、当前最大顺序号读取、下一个顺序号分配和 `updated_at` 更新；同一事务内完成消息与会话更新，不修改 P0.1 表结构。
- [x] 2.3 在 `app/composition/conversation.py` 提供 Session → Repository → 应用服务的组装入口，并验证具体 Repository 未在模块或接口层实例化。

## 3. 写入行为验证

- [x] 3.1 新增应用服务单元测试，验证空会话创建、连续创建的 UUID 隔离、首条/后续消息顺序、角色和原始内容保留。
- [x] 3.2 新增 PostgreSQL 集成测试，验证创建和追加可恢复，追加后会话更新时间更新，不存在会话或非法输入不会产生消息。
- [x] 3.3 新增并发与事务原子性测试，验证同一会话并发追加不会产生重复顺序号，写入失败不会留下部分状态。

## 4. 边界与回归

- [x] 4.1 更新架构边界测试，验证 Conversation 应用/Port 不依赖基础设施、HTTP、LLM 或 Agent，且本 Change 不新增 Conversation HTTP 路由。
- [x] 4.2 运行 Conversation 写入、存储和架构测试及目标代码 Ruff；所有新增测试必须通过。
- [x] 4.3 运行全量后端测试和现有 `/api/v1/llm/chat` 回归测试，确认 P0.1 与 V1 行为不变。
