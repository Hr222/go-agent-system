## Context

最近的流式多轮对话 Change 已将 Conversation 的创建、消息写入和最近历史读取放入独立的同步 Worker，并让 Provider 流期间不持有 Conversation Session。但 `/api/v1/interaction/chat/stream` 的统一交互准备仍从请求级 `ApplicationContainer` 取得能力目录 Repository；该容器同时组装候选检索、Embedding 和结构化识别。由于 FastAPI 的请求级 `yield` 依赖会在 `StreamingResponse` 完成后才清理，请求级 Session 和 LLM 客户端可能陪伴整个模型流。

当前 `CapabilityCandidateRetrieval` 还由每个请求容器创建。它按权限范围维护索引，但实例本身不跨请求，因此首个识别请求会重复读取完整能力目录并生成全量 Embedding。候选检索和目录复核均为同步调用，直接从异步 SSE 路由的准备阶段执行。持久化门面则在第一次取消后等待 Worker 收口；等待期间的第二次取消会被宽泛异常捕获吞掉，调用方可能在 Worker 完成前继续释放 Conversation 轮次租约。

本 Change 只修复生命周期和执行边界，不改变交互识别、风险策略、Conversation 事实、SSE 外形或多进程部署能力边界。

## Goals / Non-Goals

**Goals:**

- 在单个后端进程内共享候选索引实例，按规范化权限范围缓存并安全复用已成功构建的索引。
- 让交互准备中的同步目录查询、Embedding 和结构化识别在受控 Worker 中运行，不阻塞事件循环。
- 让流式 Chat 使用进程级运行时和短生命周期准备资源；请求级 Session 不跨越模型流。
- 保持候选权限隔离、目录复核、通用 Chat 回退、确认状态、Conversation 轮次租约和既有错误映射。
- 在重复取消时持续等待已启动的持久化 Worker 完成提交或回滚及 Session 关闭，再释放轮次租约。
- 用稳定替身、异步调度测试和 PostgreSQL 测试验证缓存复用、事件循环可用性、资源释放与事实一致性。

**Non-Goals:**

- 不把所有同步 Repository 迁移为 `AsyncSession`，不改变同步 HTTP 读写接口。
- 不把候选索引扩展为跨进程、跨实例或持久化缓存；进程重启后的重建仍是既有边界。
- 不引入后台队列、fire-and-forget 持久化、Redis、分布式锁或新的 Conversation 状态模型。
- 不修改候选召回算法、意图识别提示、通用 Chat 回退策略、上下文窗口和 Token/字符预算。
- 不改变前端事件处理、HTTP 字段、SSE 事件名称或公开错误码。

## Decisions

### 1. 候选索引由进程级服务持有，目录访问使用独立短资源

在 Composition Root 提供一份进程级 `CapabilityCandidateRetrieval`，其索引状态按规范化权限集合分区。首次访问某个权限范围时只构建一次；并发请求通过同一范围的同步协调保护“检查并构建”临界区，避免同时触发全量 Embedding。索引替换采用完整快照，构建失败时继续保留同一范围的旧索引，绝不借用其他权限范围。

进程级候选服务不能保存请求级 `CapabilityCatalogPort`。刷新索引时通过专用的目录快照/Session 工厂创建短生命周期目录访问，完成查询后立即关闭；交互准备 Worker 中的 Gateway 仍使用该次准备自己的 Session 做最终目录复核。Embedding 客户端作为无请求状态的进程级资源共享，并在应用生命周期结束时关闭。

选择“进程级索引 + 短目录访问”而不是直接把当前 `ApplicationContainer` 放入 `lru_cache`，是因为后者会把某个 HTTP Session 永久绑定到缓存服务，既不能在请求结束后安全复用，也会把已关闭 Session 带到后续请求。当前没有能力目录热更新事件，因此保留显式 `invalidate`/刷新入口；目录更新路径接入后应使受影响权限范围失效，未接入更新时索引在进程内保持既有数据快照语义。

### 2. 统一交互准备使用专用同步 Worker

流式路由使用与普通同步接口不同的依赖装配：流式 Conversation Runtime、候选检索缓存、Embedding 客户端、Proposal Store 和 Agent turn executor 使用进程级实例；每一次 `prepare` 在 Worker 内创建一个新的 `SessionLocal` 和临时 Gateway/目录适配器，完整执行候选就绪检查、目录读取、Embedding 和结构化 LLM 调用，然后提交/回滚并关闭 Session。

异步 Application 只等待该 Worker 的结果，不能把同步 `recognize()` 直接调用放在事件循环中。准备完成后返回的 `InteractionStreamPreparation` 只包含后续流所需的领域快照和安全事件数据，不携带 Repository、Session 或请求容器。确认接口继续使用它自己的短 HTTP 请求资源；本 Change 不把确认执行链改造成流式长生命周期依赖。

这样既保留 Gateway 的服务端目录校验和权限边界，也使 `StreamingResponse` 开始时不再依赖请求级数据库 Session。流式 Conversation 的 assistant 持久化继续由已有异步持久化 Port 使用另一个独立短 Session 完成。

### 3. Provider 流和请求资源采用进程级/短操作分层

流式路由只依赖一个可复用的流式 Application。它的 LLM client factory 和 Conversation Runtime 由应用生命周期管理，在请求结束时不关闭；每次请求的数据库资源仅存在于准备 Worker 或 Conversation 持久化 Worker 的短操作内。SSE 生成期间不保存交互目录 Session，也不保存 Conversation Session。

如果准备失败，Worker 在返回受控错误前完成回滚和关闭；如果准备成功，后续 `stream()` 只消费准备结果并运行既有流式 Conversation 逻辑。现有首个活动超时只覆盖 Provider 流开始后的等待，不把准备 Worker 的同步耗时误报为 Provider 超时；准备自身的异常沿用既有交互不可用映射。

### 4. 重复取消采用“直到 Worker 完成”的监督循环

`ThreadedStreamingConversationPersistence._run()` 创建的 Worker Task 使用 `shield`，第一次取消只记录原始取消并进入收口循环。收口循环反复等待被 shield 的 Task；如果等待期间再次收到 `CancelledError`，继续等待而不是退出；Worker 成功、失败或取消后均通过一次受控的结果消费收口 Task，最后重新抛出第一次取消。

该逻辑不取消正在运行的同步线程，也不把异常吞成成功。Worker 自己仍在 `finally` 中关闭 worker、回滚未提交事务并关闭 Session；只有它完成后，外层 Dialogue Runtime 才能释放 Conversation 租约。增加至少一次双重取消测试，断言租约释放事件晚于 Session 关闭事件。

### 5. 保持失败、安全和可观测性边界

候选索引不可用、目录不可用、结构化 LLM 失败、Conversation 访问拒绝、持久化失败和 Provider 失败继续映射到现有受控结果，不把缓存优化变成默认能力或越权执行。日志只记录权限范围摘要、操作阶段、耗时和稳定错误码，不记录用户原文、消息正文、Token、密钥或完整权限明细。

通过单元测试覆盖 Worker 未阻塞事件循环、同范围只构建一次、不同范围不串用、重复取消和资源收口；通过架构测试检查流式路由不直接调用同步 Gateway/Repository；通过 PostgreSQL 测试确认目录/Conversation 事实没有因 Session 拆分而改变。

## Risks / Trade-offs

- [进程级索引在目录更新后暂时陈旧] -> 提供显式按权限范围失效/刷新入口；刷新失败保留同范围旧快照，不跨权限回退。
- [短 Worker 增加线程切换和连接池压力] -> 每次准备和持久化操作只创建一个短 Session，不在模型流期间占用连接，并用并发测试记录连接释放。
- [结构化识别等待时间增长后请求仍可能受 HTTP 代理超时影响] -> 只保证事件循环不被同步调用阻塞；排队进度和准备超时协议另立 Change。
- [进程级共享客户端或候选服务在关闭时仍有请求使用] -> 通过应用 lifespan 管理关闭顺序，并在测试中验证正在进行的流不会由请求级依赖提前关闭。
- [多进程部署仍可能各自重复构建索引] -> 明确缓存和会话协调均限于单进程，不以本 Change 宣称跨进程一致性。

## Migration Plan

1. 增加候选索引的进程级装配、权限范围协调和显式失效能力；保留现有测试注入方式。
2. 增加交互准备 Worker Factory，将目录 Session、同步 Gateway 识别和准备阶段资源收口移入 Worker。
3. 调整流式路由依赖，使其使用进程级流式 Application；保留非流式确认和其他同步 HTTP 接口的原有请求级依赖。
4. 修正持久化重复取消监督循环，补充单元、架构、异步并发和 PostgreSQL 回归测试。
5. 执行相关 pytest、全量 pytest、Ruff、`compileall`、`git diff --check` 和 `openspec validate --strict`。

回滚时可恢复旧的流式依赖装配和同步准备调用；本 Change 不修改数据库结构、不需要数据迁移。回滚前必须确保进程级 LLM client 和候选缓存的关闭逻辑不会被新旧两套依赖重复执行。

## Open Questions

- 当前能力目录没有明确的热更新通知机制；本 Change 只提供失效入口，是否由目录管理 Change 自动调用由后续工作决定。
- 是否为准备 Worker 使用独立的有界执行器，取决于部署阶段对并发准备量和数据库连接池的容量评估；首版可复用受控默认线程池，但必须保留并发测试证据。
