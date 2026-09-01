## 1. 候选索引生命周期

- [x] 1.1 将 `CapabilityCandidateRetrieval` 及 Embedding 客户端改为进程级组装，保留按规范化权限范围隔离的索引状态；验收：同一进程相同权限范围的第二次识别不再触发目录全量读取或全量索引 Embedding，不同权限范围仍不共享候选。
- [x] 1.2 为候选索引增加并发构建保护、完整快照替换和显式权限范围失效入口；验收：相同范围的并发首次请求只构建一次，构建失败保留旧索引且不会串用其他范围。
- [x] 1.3 为目录刷新使用短生命周期 Session/目录工厂，并更新 Composition Root 的装配；验收：进程级候选服务不持有请求级 Repository 或 Session，目录访问完成后 Session 可关闭。
- [x] 1.4 增加候选检索单元测试和 Application Container 装配测试，覆盖跨请求复用、并发首次构建、刷新失败和权限隔离；验收：相关 pytest 全部通过。

## 2. 交互准备异步边界

- [x] 2.1 增加统一交互准备的 Worker Port/Factory，在 Worker 内创建独立 `SessionLocal`，执行 Gateway 识别及目录复核后提交/回滚并关闭资源；验收：同步目录查询、Embedding 和结构化 LLM 调用不在事件循环线程执行。
- [x] 2.2 将流式 Chat 路由切换到进程级流式 Application 和异步准备入口，准备结果不得携带 Session、Repository 或请求级容器；验收：SSE 开始前准备资源已关闭，Provider 流期间不再持有请求级交互 Session。
- [x] 2.3 保留确认接口及其他同步 HTTP 接口的既有依赖和错误映射，确保通用 Chat 回退、批准事件、澄清和失败结果不变；验收：现有 Interaction HTTP 测试和 SSE 契约测试通过。
- [x] 2.4 增加异步调度与资源生命周期测试，使用阻塞替身证明事件循环可继续运行，并验证准备失败时 Worker 回滚、Session 关闭和受控错误返回；验收：测试不依赖真实外部 Embedding 或 LLM 服务。

## 3. 持久化取消收口

- [x] 3.1 修正 `ThreadedStreamingConversationPersistence._run()` 的取消监督循环，使重复取消不会打断对已启动 Worker Task 的等待，并消费 Worker 的成功/失败终态；验收：第二次取消后请求仍保持原始取消语义，Worker 不遗留后台异常。
- [x] 3.2 增加双重取消和租约顺序回归测试，断言 Conversation 轮次租约在 Worker 事务收口及 Session 关闭之后释放；验收：user 写入、assistant 写入和 Worker 异常场景均有覆盖。

## 4. 集成验证与文档

- [x] 4.1 增加架构边界检查，禁止流式路由直接调用同步 Gateway/Repository，禁止流式运行时接收请求级 Conversation Session；验收：架构测试通过且依赖扫描无新增越界。
- [x] 4.2 运行普通流式 Conversation 的 PostgreSQL 集成测试，验证 user/assistant sequence、权限目录复核、失败事实和连接释放；验收：真实 PostgreSQL 测试通过，未产生数据库迁移或模型变更。
- [x] 4.3 运行全量 pytest、Ruff、`compileall`、`git diff --check` 和 `openspec validate --strict`；验收：所有命令通过，并记录仍不在本 Change 范围内的多进程限制。
