## Context

`/api/v1/interaction/intent` 和提议确认接口是异步 FastAPI 路由，但其应用调用仍是同步的。识别路径可能执行目录查询、候选 Embedding 和结构化 LLM；确认路径可能执行 Chat、知识检索或策略复核。任何一个上游慢调用都会占用事件循环线程。

流式 Chat 已有独立的准备 Worker。该 Worker 在生成 `approval_required` 前会写入 Conversation 的用户消息、`confirmation_required` 事件和进程内 pending invocation。若调用方在准备等待期间取消，受保护的同步 Worker 仍会完成，但原路由不会发送批准事件，短期状态会一直保留到 TTL。

本 Change 必须保持同步适配器和现有公开协议不变，同时保证取消后的 Agent 调用有可解释的终态。

## Goals / Non-Goals

**Goals:**

- 将 `/intent` 识别和非 Agent 提议确认的同步工作放到受保护的线程 Worker 中，保证事件循环可继续调度其他请求。
- 在流式准备收到取消信号后，让仍在运行的 Worker 在关闭 Session 前消费待确认提议、记录 Agent 取消事件并提交一致事实。
- 让不同权限范围的候选索引刷新可以并行，同一权限范围仍保持单飞刷新。
- 保留原始取消语义；Worker 完成事务和资源关闭后再向调用方重新抛出取消。
- 保持权限校验、提议一次性消费、错误码、HTTP 响应和 SSE 事件名称不变。

**Non-Goals:**

- 不迁移同步 Repository 到异步 ORM，不改变数据库模型或增加迁移。
- 不增加后台队列、分布式状态、跨进程取消通知或新的恢复接口。
- 不改变正常用户点击取消、确认执行、Chat 回退和 Conversation 消息内容。
- 不迁移候选索引到外部或分布式存储，不改变候选排序、权限过滤或索引数据格式。

## Decisions

### 1. 统一使用受保护的同步调用边界

在接口层为同步 Gateway 调用创建 `asyncio.to_thread` Task，并通过现有的受保护等待工具等待其完成。首次取消只取消调用方等待，不取消无法被 Python 中断的同步线程；重复取消继续等待线程收口，随后保留原始 `CancelledError`。

`/intent` 和非 Agent 确认继续使用当前请求级容器及其错误映射。因为每个同步调用在路由返回前已完成，Session 会在依赖收尾阶段关闭，不会把 Session 交给异步流生命周期。该选择避免在本 Change 中复制整套请求级依赖装配；流式 Chat 仍使用已经存在的 Session 工厂 Worker。

### 2. 用 Worker 内取消回调收口流式 Agent 准备

交互准备 Worker 增加一个仅供内部使用的取消入口。异步门面在收到取消时立即设置线程事件，然后等待准备 Worker 完成；Worker 在准备操作返回后、关闭 Session 前检查事件。如果结果是已建立的 Agent `approval_required`，Worker 调用同步的应用层取消收口：原子消费 Proposal 和 pending invocation，并通过 `DialogueAgentInvocationService.cancel_confirmation()` 写入既有 `agent_error` 取消终态。

取消入口只接收安全的准备命令和批准事件中的 proposal/conversation 标识，不携带 Repository、Session 或 Provider 对象跨边界。正常准备结果仍是纯领域快照；取消事件在同一个短 Session 中提交，失败则回滚并关闭 Session，错误由受保护等待逻辑消费，不泄漏到已断开的 HTTP 响应。

### 3. 取消处理保持幂等和竞态安全

取消收口首先读取主体绑定的 pending invocation；若它已经被显式确认、取消或过期，则不重复写事件。Proposal Store 和 pending store 继续通过单次消费保证并发确认不会执行两次。取消路径不调用 Dispatcher、Agent Runtime 或普通目标分发器。

若取消信号在准备 Worker 已完成之后才到达，门面使用准备结果执行同一取消收口；收口操作仍在新的短 Worker/Session 中完成，并通过同步锁保证一次消费。所有取消收口均在门面重新抛出取消前完成。

### 4. 候选索引按权限范围隔离刷新锁

候选检索器使用一个很小的锁保护权限范围到刷新锁的映射，并为每个权限范围分配独立的刷新锁。目录读取和 Embedding 调用只在对应权限范围的锁内执行；不同范围可以并行，同一范围仍不会重复构建。索引指针的替换继续保持原子快照语义，失败时保留该范围的旧索引。

### 5. Composition Root 提供内部取消能力

Composition 继续负责创建 SessionScoped Worker 和应用服务；Interaction Application 暴露一个同步的准备取消操作供 Worker 调用，不把 HTTP 或 asyncio 依赖引入 platform domain。新增 Port 只描述准备 Worker 的同步生命周期，不改变已有 Application Capability 的公开 HTTP 契约。

## Risks / Trade-offs

- [同步线程无法被强制中断] → 取消时等待其自然返回并确保资源关闭；保留原始取消，避免留下未收口的数据库事实。
- [取消收口本身再次遇到数据库故障] → Worker 回滚并关闭 Session，进程内状态通过消费语义避免继续执行；记录稳定错误日志，后续可通过 Conversation 运维检查发现异常。
- [请求级 Session 在同步路由中跨线程使用] → Session 只由该次 `to_thread` 调用串行使用，路由返回前等待完成；补充测试验证事件循环活跃和依赖收尾顺序。
- [取消与显式确认同时到达] → 先消费的一方取得一次性状态，另一方得到不可用结果，不重复调用或写入终态。

## Migration Plan

1. 增加异步同步调用辅助边界，并切换 `/intent` 与非 Agent 确认路由。
2. 增加准备 Worker 的取消通知和 Agent 取消收口，补充内存替身测试。
3. 运行交互、对话、架构边界和全量后端验证；不执行数据库迁移。
4. 回滚时只需回退本 Change；公开接口和数据库结构无需迁移。

## Open Questions

无。本 Change 不引入多进程状态共享；候选索引仍是进程内快照。
