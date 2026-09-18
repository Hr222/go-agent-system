## 1. 领域模型与状态机

- [x] 1.1 创建 `app/platform/task` 的 Task、Attempt、Event、状态枚举、事件类型和领域错误；验证字段、状态和 active Attempt 不变量。
- [x] 1.2 实现创建、领取、取消、取消确认、成功提交、失败提交、退避重排队、手动重试和租约恢复的纯领域转换；非法转换不得修改对象。

## 2. Application 幂等契约

- [x] 2.1 定义受信任提交、领取、续租、取消、手动重试、成功/失败提交的命令和结果契约；为每个命令明确幂等键、输入/结果指纹和稳定冲突错误。
- [x] 2.2 实现仅用于当前 Change 的内存 Task Repository/Application service；重复命令返回原结果，不重复创建 Attempt 或 Event，旧 lease 和不同指纹提交被拒绝。

## 3. 验证与边界

- [x] 3.1 为状态转换、Attempt 唯一性、终态保护、取消、自动/手动重试、恢复和事件序列编写 Domain/Application 测试。
- [x] 3.2 为创建、领取、续租、取消、重试和终态提交编写幂等重放、冲突和旧 lease 拒绝测试；确认测试不依赖 PostgreSQL、HTTP、Worker、Tender 或外部 Provider。
- [x] 3.3 执行相关 pytest、`ruff check app tests`、`python -m compileall -q app tests`、`openspec validate introduce-task-management --strict`，完成后再勾选任务并归档 TM-01。

## 4. 架构事实同步

- [x] 4.1 更新 `ARCHITECTURE.md`、当前架构基线规格和架构测试，准确记录 TM-01 已实现的领域基础及后续未实现边界；重新验证、同步主规格并归档 Change。
