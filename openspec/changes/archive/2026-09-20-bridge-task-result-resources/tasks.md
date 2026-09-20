## 1. 资源化结果端口与存储

- [x] 1.1 定义 Task 结果资源元数据、资源清单和查询/保存 Port，明确资源只包含安全元数据且不暴露内部结果文件；完成条件：业务与平台模块可通过稳定契约保存、读取和清理资源。
- [x] 1.2 实现基于既有 `AttachmentStoragePort` 的 Tender 结果资源适配器，按 Task ID/产物序号幂等暂存并原子写入 `.runtime` 清单；完成条件：重复保存返回同一资源，清单或附件不完整时不发布部分结果。
- [x] 1.3 接入 owner、Conversation、TTL、sha256 和安全文件名校验；完成条件：主体或 Conversation 不匹配、过期和校验失败均返回统一不可用结果，并清理孤立目录。

## 2. Tender Worker 结果桥接

- [x] 2.1 将 Tender Task Executor 的成功结果交给资源化结果保存端口，保留既有 Task 状态机、lease、取消和重试边界；完成条件：成功 Task 生成资源清单，Task/Event 仍不包含文件字节或物理路径。
- [x] 2.2 为资源保存失败定义固定不可重试错误 `TENDER_RESULT_RESOURCE_STORE_FAILED`，实现部分写入回滚；完成条件：任一产物失败后已创建附件被清理且 Worker 不提交成功状态。
- [x] 2.3 补充 Tender 结果保存的成功、多文件、重放、重启恢复、主体隔离和失败清理测试；完成条件：每个规格场景有自动化证据。

## 3. Task 资源查询 HTTP 契约

- [x] 3.1 增加 Task Result Resource Application/Port 和 `GET /api/v1/tasks/{task_id}/resources?conversation_id=...` 路由；完成条件：路由只调用 Application/Port，不访问 Repository、`.runtime` 或 Storage 内部记录。
- [x] 3.2 定义资源元数据 Schema 和统一 `TASK_RESOURCES_UNAVAILABLE` 错误映射，生成现有 Attachment 下载地址；完成条件：响应不含字节、物理路径、lease、输入指纹或内部结果引用。
- [x] 3.3 补充 HTTP 主体/Conversation 隔离、未完成 Task、过期资源、分页顺序和未认证访问测试；完成条件：不匹配请求不会泄漏资源存在性。

## 4. Composition、架构与文档

- [x] 4.1 在 Composition Root 固定组装资源化 Tender Result Store 和 Task 资源查询服务；完成条件：只有固定 Tender task type 能创建异步结果资源，未配置资源依赖时不隐式降级或开放通用入口。
- [x] 4.2 增加架构边界测试，证明接口层只依赖 Application、业务/平台层不依赖 HTTP，资源 Port 不暴露数据库、文件路径或 Provider 类型；完成条件：边界测试通过。
- [x] 4.3 更新 `ARCHITECTURE.md`、系统看板和必要导出，准确记录 TM-07.5 范围，不声明 TM-08 前端、TM-09 E2E 或 Workflow 已完成；完成条件：文档与实现一致。

## 5. 验收

- [x] 5.1 执行相关 pytest、Task/Attachment 架构测试和 HTTP 路由测试；完成条件：全部通过并记录结果。
- [x] 5.2 执行 `ruff check app tests`、`python -m compileall -q app tests`、`openspec validate bridge-task-result-resources --strict` 和 `git diff --check`；完成条件：全部通过后方可归档。
