## 1. 会话锁协调能力

- [x] 1.1 在 Dialogue Application 边界实现进程内 `conversation_id` 锁注册表、可释放租约和引用回收；完成条件：同一会话只能有一个持有者，取消等待不泄漏引用，最后一个引用释放后状态被删除。
- [x] 1.2 为会话锁协调器补充独立单元测试；完成条件：覆盖同会话等待、不同会话并行、等待取消、重复释放安全和状态回收。

## 2. 普通流式轮次接入

- [x] 2.1 在 Composition/HTTP 组装中创建并向请求级 Streaming Conversation Runtime 注入同一进程共享的协调器；完成条件：请求级 Container 不会创建彼此隔离的锁注册表，测试替身仍可注入。
- [x] 2.2 重构 Streaming Conversation Runtime：先创建或解析 Conversation，取得锁后才写入 user、构建上下文和调用 Provider；完成条件：同会话后续请求等待期间不写 Message、不读上下文、不调用 Provider，不同 Conversation 保持并行。
- [x] 2.3 为 Runtime 流增加显式关闭时的一次性释放包装；完成条件：正常完成、Provider/持久化失败、取消和首个事件前 `aclose()` 均关闭底层流并释放锁，已写 user 与 assistant 的既有失败语义不变。

## 3. 交互回归与验证

- [x] 3.1 更新 Dialogue 与 Interaction 测试；完成条件：覆盖同会话 A/B 时序、A 成功后 B 读取 A 的 assistant、A 失败或取消后 B 继续、锁等待不被映射为 Provider 首活动超时、既有 SSE 外形不变。
- [x] 3.2 更新必要的 Composition/架构边界测试；完成条件：协调器只通过 Composition 注入 Runtime，普通 Chat 仍只经过既有 Streaming Conversation Runtime，Agent continuation 不受本 Change 影响。
- [x] 3.3 运行受影响 pytest、架构测试、`openspec validate serialize-streaming-conversation-turns --strict --no-interactive` 和 `git diff --check`；完成条件：命令通过且任务清单与实现一致。
