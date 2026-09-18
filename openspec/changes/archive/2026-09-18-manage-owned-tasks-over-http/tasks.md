## 1. Owner-scoped Application 与持久化查询

- [x] 1.1（对应 `owned-task-http-management`：Task 查询）定义带 `owner_subject` 的 Task 列表、详情和事件读取 Application/Port 契约，以及不含敏感字段的 Task/Event 安全投影。
- [x] 1.2（对应场景：主体隔离与分页）扩展 PostgreSQL Repository 和内存替身，按 owner 过滤 Task，提供稳定列表排序、有限分页和单 Task 递增事件读取；不改变表结构。
- [x] 1.3（对应场景：取消/重试）增加 owner admission Application，只有主体拥有任务时才调用既有取消/手动重试协调器，并将领域拒绝转换为固定安全结果。

## 2. HTTP 适配与依赖组装

- [x] 2.1（对应场景：Task 查询、事件历史）新增 `/api/v1/tasks` 路由、Pydantic Schema、Assembler 和分页参数校验，返回安全 Task/Event 投影。
- [x] 2.2（对应场景：取消/手动重试）新增 `/api/v1/tasks/{task_id}/cancel` 和 `/api/v1/tasks/{task_id}/retry` 路由，校验 command_id，复用幂等命令并映射主体、状态和策略错误。
- [x] 2.3（对应安全要求）接入 `RequestPrincipal`、Composition Root 和 API Router；证明 HTTP 层不提供创建、领取、续租、结果回写、恢复或 lease token 响应。
- [x] 2.4（对应错误隔离）统一未认证、跨主体/不存在、分页无效、非法状态和底层失败的状态码与安全错误码，不返回原始异常或敏感数据。

## 3. 测试与架构边界

- [x] 3.1 为内存 Application 增加 owner 隔离、稳定分页、事件顺序、安全投影、取消/重试幂等和策略拒绝测试。
- [x] 3.2 为 HTTP 路由增加已认证、未认证、跨主体、查询分页、事件脱敏、取消确认和手动重试重放测试。
- [x] 3.3 为 PostgreSQL 增加独立 Session 的 owner 过滤、事件读取、事务回滚和命令回执测试。
- [x] 3.4 增加架构边界测试，证明路由只依赖 Application/Assembler/Schema，Task Application/Ports 不依赖 FastAPI、ORM 或具体 Session。
- [x] 3.5 执行相关 pytest、全量 `python -m pytest -q`、`ruff check app tests`、`python -m compileall -q app tests`、`git diff --check` 和 `openspec validate manage-owned-tasks-over-http --strict`。

## 4. 架构事实与交付

- [x] 4.1 更新 `ARCHITECTURE.md`、系统看板和主规格，明确 Task HTTP 已实现但创建、Worker 内部契约、Tender、前端和 E2E 仍按后续 Change 处理。
- [x] 4.2 完成合成主体隔离 HTTP 人工验收，勾选全部任务，归档 Change，创建单独 Git commit 并推送远程。
