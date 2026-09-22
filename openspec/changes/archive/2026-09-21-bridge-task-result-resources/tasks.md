## 1. Result resource contracts and storage

- [x] 1.1 定义 Task 结果资源 Port、Application 查询用例和受控不可用错误；覆盖 owner、成功状态、Conversation 绑定和过期/损坏资源校验。
- [x] 1.2 扩展 Tender 结果存储，将会话绑定产物映射到 Attachment 存储和幂等 manifest；覆盖部分写入回滚与绑定不一致。
- [x] 1.3 在 Tender Executor 和 Composition Root 中接入结果资源保存，保证保存失败不会回写 succeeded。

## 2. HTTP and frontend projection

- [x] 2.1 增加 owner-scoped `GET /api/v1/tasks/{task_id}/resources`，由 Task 受信任元数据推导 Conversation，返回安全元数据和服务器生成下载 URL。
- [x] 2.2 扩展前端 Task API/hook 与成功任务详情，展示真实结果资源及下载入口，覆盖资源不可用状态。

## 3. Verification

- [x] 3.1 运行结果资源、Tender 异步、Task HTTP 与架构边界后端测试。
- [x] 3.2 运行前端结果资源测试和 `npm run build`。
- [x] 3.3 执行 `openspec validate bridge-task-result-resources --type change --strict`。
