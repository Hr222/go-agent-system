# 会话级串行与 FIFO 队列学习笔记

> 用途：理解多用户或多标签页同时向同一 Conversation 发送消息时，为什么会出现上下文错乱；学习从进程内串行到持久化任务队列的技术路径。
>
> 本文不是当前系统的架构基线、实施计划或 OpenSpec Change。它记录问题原理、技术选项和本项目当前选择，供后续复盘和继续学习。

## 目录

1. [先用一个 Chat 例子理解问题](#1-先用一个-chat-例子理解问题)
2. [四个基础概念](#2-四个基础概念)
3. [为什么它和票务系统是同类问题](#3-为什么它和票务系统是同类问题)
4. [Chat 中一轮 turn 的正确边界](#4-chat-中一轮-turn-的正确边界)
5. [先来先服务在技术上是什么意思](#5-先来先服务在技术上是什么意思)
6. [方案比较：从快照到持久化队列](#6-方案比较从快照到持久化队列)
7. [当前选择：进程内会话级互斥等待](#7-当前选择进程内会话级互斥等待)
8. [方案 2 的一次完整执行过程](#8-方案-2的一次完整执行过程)
9. [异常处理：按阶段看，而不是统一 catch](#9-异常处理按阶段看而不是统一-catch)
10. [与当前项目代码的关系](#10-与当前项目代码的关系)
11. [测试应该证明什么](#11-测试应该证明什么)
12. [方案 2 的边界和升级信号](#12-方案-2的边界和升级信号)
13. [面试或设计讨论时的表达框架](#13-面试或设计讨论时的表达框架)

## 1. 先用一个 Chat 例子理解问题

设用户在同一个 Conversation 中快速发送两条消息：

```text
A：帮我分析这份招标文件。
B：把结论压缩成三条。
```

用户通常期望系统按如下顺序工作：

```text
写入 A 的 user Message
  -> LLM 生成 A 的回答
  -> 写入 A 的 assistant Message
  -> 写入 B 的 user Message
  -> LLM 看到 A 的完整问答，生成 B 的回答
  -> 写入 B 的 assistant Message
```

如果 A 和 B 同时执行，可能变成：

```text
请求 A 写入 user A
请求 B 写入 user B
请求 A 读取历史时看到了 user B
请求 A 调用 LLM
请求 B 调用 LLM，此时还看不到 assistant A
```

两轮都会有问题：

- A 的上下文中出现了本不该出现的后续问题 B；
- B 看不到 A 的回答，却要求“把结论压缩成三条”；
- 如果回答完成顺序反过来，Conversation 的消息顺序会和用户意图不一致；
- 当前代码要求“当前 user 是上下文最后一条”，并发写入甚至可能令先到的 A 在已经写入 user 后直接失败。

这里不是 Provider 的并发能力不足。不同 Conversation 的 LLM 调用可以并行；问题在于同一个 Conversation 的历史是一份需要按顺序演化的共享事实。

## 2. 四个基础概念

### 2.1 共享资源

共享资源是多个请求都会读写、但不能随意并发修改的东西。本问题中的共享资源是：

```text
某个 Conversation 的下一轮上下文
```

它不是单条 Message。它包含已有消息、正在形成的一轮问答，以及下一轮应当从什么历史开始构建上下文。

### 2.2 互斥锁

互斥锁只回答一个问题：

> 现在是否允许第二个请求和第一个请求同时执行？

锁能保证同时最多一个任务获得执行权，但仅有锁不一定保证等待顺序。

```text
A 在执行
B 和 C 都在等待
A 结束
C 抢到锁，B 仍等待
```

这满足互斥，不一定满足 FIFO。

### 2.3 FIFO 队列

FIFO 是 First In, First Out，即先进入队列的任务先被处理。

```text
A 入队，排第 1 位
B 入队，排第 2 位
C 入队，排第 3 位

执行顺序必须是 A -> B -> C
```

队列只记录等待顺序。它不自动完成模型调用、错误处理或数据保存。

### 2.4 调度器或协调器

协调器把“队列”和“互斥”组合起来：

```text
1. 接受一个任务并把它放入正确的队列；
2. 只允许队首获得执行权；
3. 当前任务结束后唤醒下一个任务；
4. 跳过已经取消的等待任务；
5. 在队列清空后回收自己的内存状态。
```

对于 Chat，它的键是 `conversation_id`。因此协调器不是一个全局单队列，而是许多互不影响的小队列。

```text
Conversation A: A1 -> A2 -> A3
Conversation B: B1 -> B2

A1 与 B1 可以同时执行；A2 必须等 A1 结束。
```

## 3. 为什么它和票务系统是同类问题

票务、库存扣减、订单支付和会话串行，解决的都是“对有限资源有序占用”的问题。

| 票务系统 | 会话 Chat |
| --- | --- |
| 座位或库存 | 某个 Conversation 的下一轮执行权 |
| 一张订单 | 一次 Chat turn |
| 下单并取号 | 一个请求进入会话队列 |
| 锁座或扣库存资格 | 当前任务领取执行权 |
| 支付渠道或出票服务 | LLM Provider 调用 |
| 出票成功 | assistant Message 成功写入 |
| 取消订单 | 放弃排队任务或停止生成 |
| 超时释放座位 | 释放执行权，使下一个任务可运行 |

区别在于资源容量：票务常常是库存 `N`，而会话串行的容量固定为 `1`。同一个 Conversation 同时只应有一个正在运行的 turn。

因此，这个问题有“票务系统的同类难点”，但不意味着第一版必须实现完整票务基础设施。复杂度取决于是否需要跨进程、重启恢复、后台执行和强一致审计。

## 4. Chat 中一轮 turn 的正确边界

“一轮”不能只理解为一次 LLM HTTP 调用。为了保证上下文一致性，它至少包括以下临界区：

```text
获得该 Conversation 的执行权
  -> 写入本轮 user Message
  -> 读取历史并构建本轮上下文
  -> 调用 LLM 并产生流式内容
  -> 完整成功后写入 assistant Message
  -> 释放执行权
```

最容易犯的错误是：

```text
先写 user Message
  -> 再去等待执行权
```

这看似只把 Provider 调用串行了，但无法解决历史污染：后入队的 B 在等待期间已经被写入数据库，A 仍会在读上下文时看到 B。

因此，在“严格同会话串行”的语义中必须明确：

> 排队期间不产生 user Message；只有真正获得执行权的任务才能写入 user Message。

assistant Message 也应只在获得完整、非空回答并且写入成功后出现。不能把流式半截文本作为正式历史保存。

## 5. 先来先服务在技术上是什么意思

客户端的点击时间无法成为可靠顺序：A 可能先点击，但网络抖动后 B 先抵达服务器。因此任何 FIFO 都必须定义一个“系统认可的入队时刻”。

在显式进程内 FIFO 队列中，这个时刻是协调器成功把任务放入该 `conversation_id` 队列的时刻；在数据库方案中，它是入队事务成功提交的时刻。当前采用的会话锁方案不定义这个顺序点，因为它不提供 FIFO 契约。

所以严格的技术表述是：

> 系统按成功入队顺序执行，而不承诺按浏览器的点击时间或网络发包时间执行。

还要区分两种公平性：

| 范围 | 能否保证 |
| --- | --- |
| 同一进程、同一事件循环 | 可以按本地队列的入队顺序保证 |
| 多个 worker 或多个实例 | 内存队列不能保证，需要共享持久化协调机制 |

## 6. 方案比较：从快照到持久化队列

### 6.1 方案 1：请求级上下文快照

每次请求先写 user Message，再用自己的 `sequence` 作为读取上限。A 看不到 B 之后写入的消息，B 也能独立发起 Provider 调用。

```text
A 写 user，sequence=10，读取 <= 10
B 写 user，sequence=11，读取 <= 11
A、B 可以同时调用 LLM
```

优点是没有队列、不需要进程内共享状态，也适用于多实例。缺点是它不保证完整问答轮次的顺序：B 的上下文可能仍没有 assistant A，回答完成顺序也可能交错。

它适合“请求可独立回答”的场景，不满足当前希望的“上一轮完成后再处理下一轮”。此前的 `stabilize-conversation-context-window` 草案采用的就是这种快照思路，它与 FIFO 是不同的设计方向。

### 6.2 方案 2：进程内会话级互斥等待

为每个 Conversation 建立进程内共享的 `asyncio.Lock`；同一进程中，同一个 Conversation 同时只有一个请求能执行完整 turn，其他请求等待锁释放。

优点：

- 概念直接，适合作为第一个可运行版本；
- 不需要新增 Redis、数据库表或后台 Worker；
- 能直接阻止后续 user Message 提前写入；
- 不同 Conversation 保持并行。

代价：

- 锁只存在于内存；
- 服务重启后所有等待中的请求会中断；
- 多个 Uvicorn worker 和多个服务实例之间互相看不到锁；
- 无法从数据库查询某个等待请求的状态；
- 客户端重试仍可能形成第二个等待请求，除非另做幂等设计；
- 不定义、持久化或对外承诺严格 FIFO 顺序。

这是当前 Change 1 选择的方案。它解决“单进程内同会话不能并发执行”，不宣称解决严格 FIFO 或分布式任务调度。

### 6.3 方案 3：PostgreSQL 持久化队列

把每个 turn 记录到数据库，并保存 `queued`、`running`、`succeeded`、`failed`、`cancelled` 等状态。数据库负责分配同会话顺序、领取队首和故障恢复。

优点是可跨进程、可跨实例、可查询和恢复；代价是需要迁移、状态机、租约、幂等键、恢复策略和更复杂的 SSE 订阅方式。

```text
短事务：入队并分配顺序
短事务：领取队首、转为 running
无事务：调用 LLM
短事务：写 assistant、转为 succeeded
```

它适合需要高可用、后台执行、重连查看状态或多实例部署的阶段，不是当前的第一步。

### 6.4 Redis 或消息队列

Redis Streams、RabbitMQ、Kafka 等可以作为共享队列或后台任务基础设施。它们擅长跨进程吞吐、消费者组和异步 Worker，但不会自动保证业务正确性。

即使用了消息队列，仍然需要定义：任务幂等、数据库结果提交、失败重试、取消语义、消息重复投递和 Conversation 级顺序分区。这是“换基础设施”，不是“免除队列设计”。

## 7. 当前选择：进程内会话级互斥等待

### 7.1 目标与非目标

当前第一步的目标是：

```text
在一个后端进程内，同一个 Conversation 的普通 LLM Chat 同时只能执行一轮。
若 A 已在执行，B 等待 A 结束；A 成功、失败或取消后，B 才可以开始。
```

非目标：

- 不保证多个 worker 或多个实例之间的顺序或互斥；
- 不在服务重启后恢复等待请求；
- 不引入 `asyncio.Queue`、队列编号、数据库 turn 表、租约或后台 Worker；
- 不处理 Agent continuation；它应在后续子 Change 单独接入同一协调边界；
- 不把 Token 预算和排队混成同一个问题。预算仍是 Context Builder 的职责；
- 不改变不同 Conversation 可并行执行的事实。

### 7.2 `asyncio.Lock` 在这里做什么

协调器维护一个以 `conversation_id` 为键的锁注册表：

```text
ConversationLockRegistry
  ├─ Conversation A -> asyncio.Lock
  ├─ Conversation B -> asyncio.Lock
  └─ Conversation C -> asyncio.Lock
```

请求拿到对应锁后，才写入 user Message 并执行当前 turn：

```text
请求 A -> acquire(lock[Conversation A]) -> 写 user A -> 调用 LLM -> 写 assistant A -> release
请求 B -> acquire(lock[Conversation A]) -> 等待 A 释放后才继续
```

它没有任务对象、队首概念或后台执行循环。HTTP/SSE 请求本身就是执行者：浏览器保持连接时，它等待锁并在获得锁后输出结果；浏览器断开时，等待或正在执行的请求随取消路径结束。

### 7.3 为什么不只用一个全局锁

全局锁会把所有 Conversation 都串行，用户 A 的长回答会阻塞用户 B 的无关对话，吞吐和体验都会变差。

正确的键是 `conversation_id`：

```text
lock[conversation_id]
```

因此多会话仍可并行。同一个 Provider 的并发限制由现有的 LLM 请求治理器控制，那是另一层全局资源治理；它不能替代 Conversation 的顺序控制。

### 7.4 为什么不把锁的唤醒顺序当作 FIFO 契约

当前 Python 的 `asyncio.Lock` 对等待协程有公平性描述，但它只适用于当前事件循环。请求取消、锁对象清理、未来的多 worker 部署都会改变可观察行为。

因此本 Change 的业务契约只有：

```text
同一个 Conversation 不并发执行。
```

它不对外声明“谁先开始等待，谁一定先获得锁”，也不记录排队位置。未来确实需要严格 FIFO 时，再采用显式队列或持久化 turn 方案。

## 8. 方案 2 的一次完整执行过程

以下以已有 Conversation 为例。新建 Conversation 的普通 Chat 先创建空 Conversation，再以它的 `conversation_id` 获取对应锁；因为此时还没有 Message，不会污染其他轮次。

```text
1. HTTP 接收 A
2. 校验输入、主体和 Conversation 访问权
3. A 等待并获得 Conversation X 的锁
4. 写入 user A
5. 读取当前历史，构建上下文
6. 调用 LLM，向 A 的 SSE 持续输出 delta
7. 收到完整非空回答
8. 写入 assistant A
9. 在 `finally` 中释放 A 的锁

10. B 随后获得锁，重复步骤 4-9
```

对于 A、B 同时到达的正常流程：

```text
时间  请求 A                         请求 B
----  -----------------------------  --------------------------
t0    获得锁
t1    写 user A                      等待锁；不写 user B
t2    LLM 生成 A
t3    写 assistant A
t4    释放锁
t5                                   获得锁，写 user B
t6                                   构建的历史含 A 的完整问答
t7                                   LLM 生成 B，写 assistant B
```

第 t1 行是这个 Change 的关键验收点：B 等待锁时没有持久化 user B。

### 8.1 为什么释放必须放在 `finally`

无论成功、Provider 异常、超时、客户端取消，锁都必须被释放：

```text
try:
    执行完整 turn
finally:
    release(lock[conversation_id])
```

否则 A 一旦异常，B 就会永久等待。这里的 `finally` 不是代码风格问题，而是等待请求能够继续执行的业务保证。

### 8.2 等待锁时需要给浏览器什么反馈

这是一个产品协议决定，而不是互斥正确性的前提。第一版可以保持 SSE 连接并周期性发送 heartbeat，但不需要新增队列位置或 `queued` 事件。无论采用哪种形式，都应区分：

```text
等待锁：还没有调用 Provider
Provider 首活动等待：已经开始调用 LLM，但尚未收到首个活动
流式生成：已经开始输出或等待后续 chunk
```

当前 `UPSTREAM_TIMEOUT` 的含义应只覆盖后两类 Provider 阶段；不能因为 B 正在等待 A 的锁，就错误地把它报告为 Provider 超时。

## 9. 异常处理：按阶段看，而不是统一 catch

异常处理的第一步不是写一个很大的 `except Exception`，而是先问：当前请求是否已经写入 user，是否持有锁，是否可能阻塞后继请求？

### 9.1 状态视角

进程内方案不将任务状态持久化到数据库，但在运行时仍有清晰状态：

```text
准备校验 -> 等待锁 -> 正在执行 -> 已成功
                    |             |-> 已失败
                    |             |-> 已取消
                    -> 已取消
```

终态的共同规则是：从互斥视角看，当前请求已经结束，必须释放锁，让下一个等待请求有机会运行。

### 9.2 异常矩阵

| 发生位置 | 例子 | Message 事实 | 锁动作 | 对客户端 |
| --- | --- | --- | --- | --- |
| 获得锁前 | 空输入、UUID 非法、无权限 | 不写任何 Message | 不等待锁 | 受控输入或访问错误 |
| 等待锁 | 浏览器断开、请求被取消 | 不写 user 或 assistant | 取消等待，不持有锁 | 连接已结束，无需补发 |
| 获得锁后写 user 失败 | 数据库不可用、会话被删除 | 不保证有 user；以事务实际结果为准 | 结束并释放锁 | 持久化错误 |
| 构建上下文失败 | 历史读取失败、预算拒绝 | user 已保留；无 assistant | 结束并释放锁 | 受控上下文或服务错误 |
| Provider 首活动/空闲/总超时 | 上游无响应或卡住 | user 已保留；无 assistant | 关闭流，结束并释放锁 | `UPSTREAM_TIMEOUT` |
| Provider 返回异常或空答案 | 网络错误、Provider 5xx、空内容 | user 已保留；无 assistant | 结束并释放锁 | `UPSTREAM_UNAVAILABLE` 或流错误 |
| 生成中浏览器断开 | 用户关闭标签页 | user 已保留；不保存部分 assistant | 关闭流，结束并释放锁 | 连接已结束 |
| assistant 写入失败 | 数据库提交失败 | user 已保留；无 assistant | 结束并释放锁 | 持久化错误 |
| 协调器内部异常 | 错误处理本身抛错 | 取决于已完成到哪一步 | 请求结束，但锁必须释放 | 记录日志，避免锁永久占用 |

### 9.3 为什么失败后保留 user，但不保留半截 assistant

user Message 表示用户确实发出过的输入，是事实。Provider 失败不改变这个事实。

流式输出的半截文本不是完整回答，即使浏览器暂时看到了它，也不能作为可靠上下文写入数据库：后续模型会把它误当成完成的 assistant 回复。因而当前语义应当是：

```text
user 成功落库 + assistant 完整成功落库 = 一轮成功
user 成功落库 + 没有 assistant = 一轮未完成
```

是否在后续上下文中包含“未完成 user”，是独立的上下文策略问题。第一版不应借由会话互斥擅自改变它；需要在上下文窗口或完整 Turn Change 中单独决策。

### 9.4 进程崩溃是方案 2 的硬边界

如果进程在 A 执行期间崩溃：

- 内存锁和所有等待请求的状态消失；
- 数据库中可能已经有 user A，但不会有 assistant A；
- 客户端的 SSE 连接中断；
- 新进程没有信息知道 B 曾经等待过。

这不是漏写一个异常处理就能解决的缺陷，而是内存方案没有持久化任务事实的必然结果。要处理它，需要升级到持久化 turn、租约和恢复机制的方案 3。

## 10. 与当前项目代码的关系

### 10.1 当前普通 Chat 的执行位置

普通 Chat 的入口是：

```text
HTTP /api/v1/interaction/chat/stream
  -> InteractionChatStreamApplication.stream()
  -> StreamingConversationRuntime.execute()
  -> 写 user、读取历史、调用流式 LLM、写 assistant
```

当前 `StreamingConversationRuntime` 会先写入 user Message，再读取历史。这正是需要移动到“获得会话锁之后”的操作。

相关路径：

- `app/platform/interaction/application/chat_stream.py`
- `app/platform/dialogue/application/streaming_conversation.py`
- `app/infrastructure/persistence/repositories/conversation_write_repository.py`

### 10.2 锁注册表必须是进程共享对象

当前 HTTP 依赖会为请求创建 `ApplicationContainer` 和数据库 Session。若每个请求各自创建一份锁注册表，A、B 会得到两把不同的锁，会话互斥完全失效。

因此方案 2 的锁注册表生命周期必须是：

```text
一个后端进程
  -> 一份 ConversationLockRegistry
  -> 多个 HTTP 请求共同使用
```

它应在应用启动时创建并在应用关闭时停止，或由等价的进程级依赖提供。它不能依附于单个 HTTP Request 的 Container。测试中则为每个测试创建隔离的锁注册表。

### 10.3 它不替代现有的 Provider 治理

项目已有 `LlmRequestGovernor`，用于控制同一 Provider 的请求速率和最大并发。这是全局 Provider 资源治理：

```text
所有 Conversation 共同竞争 Provider 并发槽位
```

会话锁是 Conversation 语义治理：

```text
同一 Conversation 的 turn 不并发执行
```

两者可以同时存在。A、B 属于不同 Conversation 时，即使已经通过会话锁，仍可能在 Provider 并发治理处等待；这不破坏会话内部的互斥语义。

### 10.4 同步数据库访问是另一个问题

Conversation Repository 当前使用同步 SQLAlchemy Session，而普通 Chat 是异步流式路径。进程内互斥只解决“能否同时执行”，不解决“同步数据库操作会不会阻塞事件循环”。

后者应在“异步持久化访问”子 Change 中处理，例如用独立短生命周期 Session 和清晰的异步执行边界。不能因为引入会话锁就把两个问题混在一处扩张实现范围。

### 10.5 Agent continuation 暂不接入

Tender Agent 的 continuation 最终也会向同一 Conversation 写 assistant Message。因此它未来应复用同一 Conversation 执行边界，否则仍可能与普通 Chat 交错。

但是 continuation 的触发点、同步 LLM 调用、Agent result 读取和确认流程都不同。第一步只覆盖 `chat.general`；在子 Change 2 中再用 Tender Agent 验证 continuation 的接入语义。

## 11. 测试应该证明什么

会话互斥的测试不能只验证“方法被调用了”。应使用可控制的 Fake Streaming LLM，让 A 的流停在中间，观察 B 是否真的没有越过 A。

最小测试集：

| 场景 | 必须证明的事实 |
| --- | --- |
| 同会话 A、B 并发 | B 的 LLM 在 A 释放锁前没有开始；B 的 user 在 A 完成前没有写入 |
| A 完成后 B 开始 | B 构建的历史中包含 A 的 assistant Message |
| 不同会话 A、B 并发 | 两个 LLM 都能开始，未被全局串行化 |
| A Provider 失败 | A 不写 assistant，B 不永久阻塞，随后能获得锁 |
| A 生成中取消 | Provider 流被关闭，A 不写部分 assistant，B 随后能获得锁 |
| B 等待锁时取消 | B 不写 user，A 完成后 B 不再执行 |
| user 写入失败或上下文失败 | 锁被释放，后续请求仍可执行 |
| 空锁清理 | Conversation 完成后注册表不无限保留未使用的锁 |
| 进程级共享 | 两个独立的 HTTP 请求路径使用同一锁注册表，而不是各建一个 |

还应检查 SSE 错误语义：等待锁不能消耗 Provider 首活动超时，也不能被错误报告为上游不可用。

## 12. 方案 2 的边界和升级信号

方案 2 不是错误方案，只是有明确适用范围。当出现下列信号时，应考虑单独建立持久化队列 Change：

- 部署从单个 Uvicorn 进程变成多个 worker；
- 部署到多个容器或多个实例；
- 用户需要断线后仍让任务完成，或重新连接后查看任务状态；
- 任务开始包含较长的 Agent、文件处理或外部业务动作；
- 服务重启不能再接受丢失排队任务；
- 需要客户端幂等重试、人工取消、审计或运营监控；
- 需要按队列长度、等待时间、失败率做容量治理。

升级时通常会引入持久化 `turn` 事实、状态机、租约和幂等键。那是合理演进，不是说明进程内方案写错了。

```text
阶段一：单进程会话互斥，解决上下文并发污染
  -> 阶段二：Agent continuation 接入同一会话执行边界
  -> 阶段三：按完整 Turn 选择上下文窗口
  -> 阶段四：需要高可用时，持久化队列和恢复机制
```

## 13. 面试或设计讨论时的表达框架

遇到“如何保证 FIFO”或“如何处理同资源并发”时，不要先说 Redis、Kafka 或数据库锁。先用下面顺序拆问题：

1. 资源是什么，粒度是什么？
   - 本题是每个 `conversation_id`，不是整个 Chat 服务。
2. 正确性不变量是什么？
   - 当前第一步只要求同一 Conversation 同时一个 turn；不同 Conversation 可并行。
3. 是否需要顺序契约？
   - 当前不需要；未来要求 FIFO 时，顺序应以成功入队为准，而不是客户端点击时间。
4. 一个任务的原子边界是什么？
   - 获得执行权到 user/assistant 事实完成或终止。
5. 失败后怎样保证后继请求不被卡死？
   - 所有执行路径在 `finally` 释放会话锁；持久化方案再加 lease 恢复崩溃任务。
6. 部署范围是什么？
   - 单进程可用内存锁；多实例必须共享协调状态。
7. 用户体验和重试语义是什么？
   - 等待如何反馈、断开是否取消、是否需要幂等键。

一句话总结：

```text
先定义资源、顺序点和失败语义，
再按部署范围选择进程内互斥、显式 FIFO 队列、数据库队列或消息中间件。
技术选型是最后一步，不是第一步。
```
