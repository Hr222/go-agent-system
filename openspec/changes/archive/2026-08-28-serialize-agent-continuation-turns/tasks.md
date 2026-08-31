## 1. 共享协调器接入确认入口

- [x] 1.1 将进程共享的 `ConversationTurnCoordinator` 从 Composition Root 注入 `InteractionChatStreamApplication`，并保留请求级容器之间的同一实例；完成条件：组合测试能证明普通 Chat 与确认 Agent 使用同一协调器，测试替身仍可显式注入。
- [x] 1.2 将对话 Agent 确认应用入口和 HTTP 路由改为异步调用；完成条件：HTTP 响应字段、确认协议和既有错误映射不变，确认入口可以等待会话租约且取消异常不会被转换成普通业务失败。

## 2. 确认后的 Agent 轮次串行化

- [x] 2.1 在 `confirm` 动作中先读取主体绑定的 pending invocation 以定位 `conversation_id`，取得会话租约后再消费 proposal 与 pending invocation；完成条件：锁等待期间取消不会消费一次性状态、启动 Agent、调用 continuation 或写入 Conversation 事实，取消动作保持原有语义。
- [x] 2.2 让租约覆盖 Agent 调用、Agent 结果或错误事实持久化、continuation 上下文构建、LLM 调用及 assistant Message 写入，并在所有成功、失败、访问拒绝和取消路径释放；完成条件：同会话普通 Chat 不会与 Agent 交错，不同会话可以并行，Agent/continuation 失败后后续轮次可继续。
- [x] 2.3 保持既有一次性 proposal 与 pending invocation 的幂等消费和受控响应；完成条件：同一 proposal 的并发确认最多执行一次 Agent，失效或重复确认不产生第二份 Agent 结果事实，既有 `GatewayResult` 外形保持不变。

## 3. 时序与边界回归测试

- [x] 3.1 使用受控 Tender Agent、continuation 和普通 Chat 替身补充同 Conversation 时序测试；完成条件：覆盖 Agent 进行中阻塞普通 Chat、Agent 完成后普通 Chat 读取完整 assistant、不同 Conversation 并行，以及 Agent/continuation 失败后锁释放。
- [x] 3.2 补充确认等待取消与并发确认测试；完成条件：取消前 proposal/pending 仍可重试且无新增事实，并证明重复确认不会重复调用 Agent；覆盖主体隔离和 proposal 失效的既有拒绝语义。
- [x] 3.3 更新必要的 Composition 与架构边界测试；完成条件：确认入口仅通过 Composition 获得共享协调器，Dialogue continuation 不直接依赖协调器，接口层只负责 await 应用入口和响应组装。

## 4. 严格验证与任务收口

- [x] 4.1 运行受影响 pytest、架构测试、`ruff check app tests` 和 `python -m compileall -q app tests`；完成条件：所有命令成功且新增时序测试稳定通过。
- [x] 4.2 运行 `openspec validate "serialize-agent-continuation-turns" --strict --no-interactive` 与 `git diff --check`，核对实现、spec 和任务清单；完成条件：严格校验与 diff 检查通过，且仅在对应验证证据存在后勾选全部任务。
