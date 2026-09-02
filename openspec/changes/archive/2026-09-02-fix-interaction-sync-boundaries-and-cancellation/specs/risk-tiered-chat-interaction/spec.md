## ADDED Requirements

### Requirement: 不同权限范围的候选索引刷新不得相互阻塞

系统 MUST 只对同一权限范围的候选索引刷新进行串行化；一个权限范围的目录读取或 Embedding 调用变慢时，其他权限范围 MUST 仍可开始或完成自己的索引刷新。

#### Scenario: 慢权限范围不阻塞其他范围

- **WHEN** 权限范围 A 的候选索引刷新正在等待 Embedding 返回
- **THEN** 权限范围 B 的候选索引刷新可以执行目录读取和 Embedding
- **AND** 同一权限范围 A 的第二次刷新仍等待第一次刷新完成

### Requirement: 普通交互接口的同步工作不得阻塞事件循环

系统 MUST 在异步 HTTP 路由执行同步的 Gateway 识别、候选目录读取、Embedding、结构化 LLM 或非 Agent 受控分发时，将该工作放入受保护的同步 Worker 边界。同步 Worker 完成前，路由不得提前释放其请求资源；Worker 完成后才返回既有受控响应。

#### Scenario: 意图识别上游阻塞时其他异步任务仍可运行

- **WHEN** `/api/v1/interaction/intent` 的目录、Embedding 或结构化识别调用被阻塞
- **THEN** 事件循环仍能执行其他不相关的异步任务
- **AND** 识别完成后返回既有的授权、待确认、澄清或失败响应

#### Scenario: 非 Agent 确认目标阻塞时其他异步任务仍可运行

- **WHEN** 非 Agent 提议确认触发 Chat、知识检索或策略复核且目标调用被阻塞
- **THEN** 事件循环仍能执行其他不相关的异步任务
- **AND** 目标完成后返回既有的完成、拒绝或失败响应

#### Scenario: 同步 Worker 被取消时资源先收口

- **WHEN** 调用方在同步 Worker 尚未完成时取消 HTTP 操作
- **THEN** 系统等待 Worker 完成并关闭其使用的资源
- **AND** 系统重新抛出原始取消，不把取消伪装成成功结果

### Requirement: 流式准备取消不得遗留不可操作的 Agent 提议

系统 MUST 在流式 Chat 准备阶段已建立 Agent 待确认状态但客户端在收到 `approval_required` 前断开时，消费该主体绑定的一次性提议和 pending invocation，并记录既有的 Agent 取消终态。系统 MUST NOT 调用 Agent Runtime、普通分发器或执行目标能力。

#### Scenario: 批准事件尚未发送时客户端断开

- **WHEN** Agent 准备已写入 `confirmation_required` 事实但 SSE 批准事件尚未发送，且调用方取消请求
- **THEN** 系统写入 `AGENT_CALL_CANCELLED` 终态并释放短期待确认状态
- **AND** Conversation Session 在取消事实提交或回滚后关闭

#### Scenario: 取消与确认并发竞争

- **WHEN** 客户端断开触发取消，同时另一个请求确认同一提议
- **THEN** 只有先原子消费提议的一方能够改变该提议状态
- **AND** 系统最多执行一次 Agent 调用且不会写入重复取消终态

#### Scenario: 准备未建立 Agent 状态时取消

- **WHEN** 普通 Chat、澄清、拒绝或准备失败结果在 SSE 开始前被取消
- **THEN** 系统不创建或取消 Agent 提议
- **AND** 系统关闭准备 Worker 资源并保留原始取消语义
