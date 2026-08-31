## Context

当前 Conversation 的 Access、Message Write 和 History Read Application 使用同步 SQLAlchemy `Session`。普通流式 Chat 通过异步 HTTP/SSE 入口调用 Dialogue Runtime；如果 Runtime 直接调用这些同步服务，数据库等待会占用事件循环。模型生成又可能持续较长时间，因此不能把一个请求级 Session 从 user 写入一直保留到 assistant 写入。

父树已经定义了普通流式对话的业务事实：user Message 先持久化，读取当前会话上下文后调用 Provider，只有完整非空回答才保存 assistant Message；既有 Conversation 轮次租约覆盖完整轮次，同一会话串行、不同会话可并行；上下文窗口按本轮 user 的 sequence 截止。这个子 Change 只改变同步持久化操作的执行位置和资源生命周期。

工作区中已有一份未提交的试探性实现，可作为实现参考，但不能替代本 Change 的测试和验收证据。

### 普通流式 Chat 持久化操作矩阵

| 阶段 | 异步 Runtime 行为 | Worker/Session 边界 | 保持不变的业务事实 |
| --- | --- | --- | --- |
| 创建或解析 | 使用可信主体创建新会话，或解析主体已准入的会话 | 一个独立同步 Worker 完成短操作后提交/回滚并关闭 Session | 不接受客户端 owner；不存在、越权和主体缺失沿用既有拒绝类别 |
| user 写入 | 在已取得轮次租约后追加本轮 user Message | 一个新的独立同步 Worker/Session | user 先写入；sequence 由 Conversation 写入端口分配 |
| 最近上下文读取 | 以本轮 user 的 sequence 作为 `through_sequence`，按策略上限读取窗口 | 一个新的独立同步 Worker/Session | 只读同一会话；sequence 截止、连续后缀、预算和消息顺序保持不变 |
| Provider 流 | 使用已关闭前置操作的领域快照构建请求并消费流 | 不持有 Conversation Session 或数据库连接 | 轮次租约持续覆盖生成；SSE、取消、上游失败和空回答语义保持不变 |
| assistant 写入 | 仅在完整非空回答形成后追加 assistant Message | 一个新的独立同步 Worker/Session | 写入成功后才发送既有完成事实；失败不伪造 assistant 历史 |

以上边界确认：轮次租约覆盖 user 写入至 assistant 终态，Worker 不持有租约；异步取消必须等待当前 Worker 的提交/回滚和 Session 关闭后再释放租约；该 Change 不改变主体、sequence、租约、上下文预算或失败语义。

## Goals / Non-Goals

**Goals:**

- 让异步流式 Dialogue 不直接在事件循环中执行同步 Conversation 数据库操作。
- 让创建/解析会话、user 写入、最近上下文读取和 assistant 写入都经过明确的异步持久化边界。
- 每个短操作使用独立 Session，完成提交或回滚后立即关闭。
- Provider 流式生成期间不持有 Conversation Session 或数据库连接。
- 保持父树中的消息顺序、sequence、主体访问、上下文、SSE、失败和取消语义。
- 在请求取消、Worker 异常和持久化失败时回收 Worker、Session 和既有轮次租约。

**Non-Goals:**

- 不把全部 Conversation Application、Repository 或同步 HTTP 路由迁移为 `AsyncSession`。
- 不引入后台队列、fire-and-forget 写入、Redis、分布式锁或新的 Conversation 状态模型。
- 不改变 `ConversationTurnCoordinator` 的互斥范围、顺序语义或跨进程能力边界。
- 不改变 Context Builder、sequence 截止、预算、摘要、Agent invocation 或 Agent continuation 的业务规则。
- 不处理 Interaction 能力目录、Embedding 或其他非 Conversation 数据库调用的全面异步化。

## Decisions

### 1. 在 Dialogue 边界增加异步持久化 Port

普通流式 Runtime 依赖一个只表达异步操作的 Conversation 持久化 Port，而不接收 SQLAlchemy `Session`、Repository 或 ApplicationContainer。该 Port 至少提供会话创建/解析、消息追加和最近消息读取能力。

这样可以保持 Conversation Domain、Application 和现有同步 Port 的稳定性，也让测试可以注入内存或阻塞替身。把同步方法简单标记为 `async` 不足以解决事件循环阻塞，因此同步实现必须在边界外的 Worker 中执行。

备选方案是全面迁移到 SQLAlchemy `AsyncSession`。该方案长期可行，但会同时影响所有 Conversation 服务、同步 HTTP 路由、测试夹具和 Agent 依赖，超出本子 Change 的必要范围。

### 2. 每次短操作使用独立同步 Worker 和 Session

Composition Root 注入 Worker Factory。每个异步 Port 操作在 Worker 线程中创建一个新的 `SessionLocal`，组装现有 Conversation Service/Repository，执行一个短操作，并在 `finally` 中关闭 Session。Repository 现有的提交、回滚和领域错误保持不变。

操作边界如下：

```text
创建/解析会话  -> 短事务 -> 关闭 Session
写入 user      -> 短事务 -> 关闭 Session
读取上下文     -> 短事务 -> 关闭 Session
Provider 流     -> 不持有 Conversation Session
写入 assistant  -> 短事务 -> 关闭 Session
```

第一版使用 `asyncio.to_thread` 或等价的受控线程执行边界，不建立独立持久化队列。线程和数据库连接池的容量必须通过测试和运行配置验证，不能用无限制的后台任务掩盖资源不足。

### 3. 轮次租约与持久化 Worker 分工

已有 Conversation 轮次租约仍由 Dialogue Runtime 持有，覆盖 user 写入、上下文读取、Provider 流和 assistant 写入。租约不进入 Worker，也不绑定到数据库事务。

对已解析的 Conversation，Runtime 必须先取得租约，再写入 user。user 提交后取得其 sequence，使用该 sequence 读取上下文；Provider 流结束并形成完整回答后，再启动独立的 assistant 写入操作。这样异步化不会引入第二套锁，也不会改变同会话事实顺序。

### 4. 取消和异常必须等待同步操作收口

异步调用被取消时，不能让已经启动的同步数据库函数在后台无人管理地继续运行，也不能在它完成前释放会话租约。持久化门面应屏蔽请求取消对 Worker Task 的直接连带取消，并等待 Worker 完成关闭或回滚；完成后重新抛出原有取消语义。

Provider 流被取消或失败时，Runtime 关闭底层模型流，不写入部分 assistant，并释放轮次租约。若 assistant 写入本身失败，已提交的 user 和模型流事实不被伪造为 assistant 成功。

### 5. 请求级 Session 不进入流式持久化运行时

普通流式 Runtime 只接收异步持久化 Port，不接收 HTTP 请求级 Session。同步 Conversation HTTP 接口仍可使用其请求级 Session；两条路径的生命周期不能混用。

流式请求中如果路由准备阶段使用了其他同步能力，准备结果必须在模型流开始前完成，且该 Session 不得被 Conversation Runtime 或 Provider 流继续使用。与 Conversation 无关的 Interaction 数据库调用不在本 Change 的全面异步化范围内。

### 6. 错误、权限和外部契约保持原样

Access 校验继续由 Conversation Application 执行，异步适配器不接受客户端提供的 owner 或权限替代值。访问拒绝、输入错误、上下文预算失败、Provider 失败、空回答和 assistant 写入失败继续沿用已有错误映射；不新增公开错误码或 SSE 字段。

## Risks / Trade-offs

- [线程切换和每次创建 Session 增加短操作开销] → 只把短数据库操作放入 Worker，Provider 流期间不占用连接，并用真实 PostgreSQL 验证连接释放。
- [线程池或数据库连接池耗尽] → 不创建无界后台任务；增加并发/阻塞测试，记录连接池配置为后续容量评估依据。
- [取消发生在提交临界点] → Worker 操作使用 shield 和 finally 收口，取消只影响调用方等待结果，不破坏已完成事务。
- [请求级容器仍可能装配其他同步能力] → 架构测试确认 Streaming Runtime 不接收请求级 Session；将 Conversation Session 生命周期与其他 Interaction 依赖分开验证。
- [同步 Repository 将来需要真正异步化] → 保留稳定的异步 Port，未来可替换为 AsyncSession Adapter，不改变 Dialogue 业务契约。

## Migration Plan

1. 增加 Dialogue 异步持久化 Port、Worker Factory 和 Composition 适配器，保留所有现有同步 Conversation 服务。
2. 将普通流式 Runtime 的会话访问、user 写入、上下文读取和 assistant 写入切换到该 Port。
3. 增加阻塞、取消、Session 生命周期和 PostgreSQL 集成测试，确认轮次租约、sequence 和失败语义没有变化。
4. 通过全量后端测试、架构边界检查、Ruff、`compileall`、`git diff --check` 和 OpenSpec 严格校验后再同步正式规格并归档。

回滚时恢复 Runtime 对原同步 Conversation 服务的组装即可；本 Change 不修改数据库结构和已有数据，不需要数据迁移或数据回滚。

## Open Questions

- 生产环境是否需要为持久化 Worker 使用独立的有界 `ThreadPoolExecutor`，还是先复用 `asyncio.to_thread` 的默认执行器。
- 是否需要为持久化短操作增加统一耗时、失败类型和连接池等待指标；本 Change 至少保留可诊断日志，不记录消息正文或敏感数据。
- 后续是否将 Conversation 的全部 HTTP 读写入口逐步迁移到真正的异步数据库适配器，由独立 Change 决定。
