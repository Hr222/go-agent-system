## 1. 异步同步调用边界

- [x] 1.1 为同步操作增加可复用的受保护线程等待入口；验收：首次或重复取消不会让已启动的同步 Worker 遗留后台任务，并保留原始取消语义。
- [x] 1.2 将 `/api/v1/interaction/intent` 的 Gateway 识别切换到线程 Worker；验收：阻塞目录/Embedding/结构化 LLM 替身期间事件循环仍可运行，成功和失败响应契约不变。（对应 `risk-tiered-chat-interaction`）
- [x] 1.3 将非 Agent 提议确认的同步 Gateway 分发切换到线程 Worker；验收：阻塞 Chat/RAG/策略目标期间事件循环仍可运行，提议仍只消费一次且响应契约不变。（对应 `risk-tiered-chat-interaction`）

## 2. 流式 Agent 取消收口

- [x] 2.1 为交互准备 Worker 增加取消通知和同步收口接口；验收：收到取消信号后，Worker 在关闭 Session 前能够区分普通结果与 `approval_required` 结果。
- [x] 2.2 实现 Agent 准备取消的提议消费、pending invocation 清理和 `AGENT_CALL_CANCELLED` 事件写入；验收：断连准备不会遗留可确认状态，不调用 Dispatcher/Agent Runtime，事务完成后 Session 才关闭。（对应两个增量规格）
- [x] 2.3 覆盖取消与确认竞态及取消收口失败；验收：一次性状态最多被一方消费，数据库失败回滚且不会返回成功执行结果。

## 3. 回归验证与交付

- [x] 3.1 增加接口级和应用级异步调度测试；验收：阻塞替身证明事件循环活跃，并覆盖识别、确认、准备取消、正常批准和受控失败路径。
- [x] 3.2 增加架构边界检查；验收：异步 Interaction 路由不直接执行同步 Gateway/分发调用，既有流式资源生命周期规则不回退。
- [x] 3.3 细化候选索引刷新锁到权限范围；验收：不同权限范围的慢刷新不相互阻塞，同一范围仍保持单飞刷新且失败保留旧快照。
- [x] 3.4 运行相关 pytest、全量 pytest、Ruff、compileall、git diff --check 和 `openspec validate --strict`；验收：所有可运行检查通过并记录真实外部 PostgreSQL 测试结果。
- [x] 3.5 完成最终代码复核，确认本 Change 不包含敏感运行产物；验收：工作区仅包含本 Change 文件并通过暂存差异检查后提交 Git。
