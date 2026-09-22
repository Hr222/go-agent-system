## 1. Event query semantics

- [x] 1.1 将事件查询启用条件与轮询条件拆分，确保终态任务首次请求事件而不轮询。
- [x] 1.2 更新详情页传参，并增加活动/终态状态的 hook 回归测试。

## 2. Verification

- [x] 2.1 运行 Task Management 前端测试和 `npm run build`。
- [x] 2.2 执行 `openspec validate fix-task-workspace-event-visibility --type change --strict`。
