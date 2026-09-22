## 1. Task API boundary

- [x] 1.1 增加 Task 类型、列表/详情/事件/取消/重试 API mapper，并覆盖 snake_case 到前端 camelCase 的单元测试。
- [x] 1.2 增加 Task Query/Mutation hooks，定义活动状态轮询和精确缓存失效策略，并覆盖 hook 行为测试。

## 2. Agent workspace integration

- [x] 2.1 将 Agent 总览和 Tender Agent 任务表接入真实任务列表，覆盖加载、空列表、未授权和请求失败状态。
- [x] 2.2 将任务详情接入真实详情与事件查询，覆盖活动任务轮询、终态停止轮询和不可用状态。
- [x] 2.3 接入取消/重试命令，显示 pending/error 状态并刷新详情、事件和列表缓存；移除对应 mock 任务数据。

## 3. Verification

- [x] 3.1 运行前端 Task API/hooks/页面测试和 `npm run build`。
- [x] 3.2 运行后端现有任务 HTTP 回归测试，确认未改变后端契约。
- [x] 3.3 执行 `openspec validate connect-task-management-workspace --type change --strict`。
