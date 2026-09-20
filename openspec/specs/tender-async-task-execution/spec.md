# tender-async-task-execution Specification

## Purpose
TBD - created by archiving change run-tender-agent-as-async-task. Update Purpose after archive.
## Requirements
### Requirement: Tender 指定能力必须按固定档案进入异步 Task

系统 MUST 只为服务端登记的 `agent.tender.generate_bid_skeleton` 能力配置异步档案，并使用固定的 `tender.generate_bid_skeleton` Task 类型、尝试策略和元数据白名单。客户端输入、模型输出和协议适配器 MUST NOT 选择其他 Task 类型或执行器；未登记的 Tender 能力继续使用同步策略。

#### Scenario: Tender 生成能力被受控接收

- **WHEN** 已认证主体通过现有 Agent 授权和输入复核调用 `agent.tender.generate_bid_skeleton`
- **THEN** 系统按固定档案创建 `queued` Task 并返回 `accepted` execution reference
- **AND** Task 的 owner、task type、最大尝试次数和手动重试策略来自服务端绑定

#### Scenario: 其他 Tender 能力保持同步

- **WHEN** 主体调用 `extract_bid_format_section` 或 `verify_extraction_boundary`
- **THEN** 系统继续使用同步 Agent Runtime
- **AND** 不创建 Task、Attempt 或 Task Event

### Requirement: 异步 Tender 输入必须形成主体绑定的安全快照

系统 MUST 只接受已经由 Attachment 能力解析的服务端文档作为 Tender 异步输入。快照事实 MUST 包含确定性输入指纹、opaque attachment reference、文件名、媒体类型、哈希和可选用户焦点；Task 与事件不得保存文件字节、原始 Agent 输入、凭据或 Provider 响应。

#### Scenario: 生成附件快照

- **WHEN** 已授权调用包含主体可读的 `ResolvedAttachment` 和合法用户焦点
- **THEN** 系统生成稳定输入指纹和主体绑定的快照引用
- **AND** 快照正文留在 Attachment 存储，Task 只接收白名单内部元数据

#### Scenario: 输入不是已解析附件

- **WHEN** 异步 Tender 调用缺少 `ResolvedAttachment` 或包含多个不支持的输入来源
- **THEN** 系统返回受控输入错误
- **AND** 不创建 Task 或快照回执

#### Scenario: 快照主体不匹配

- **WHEN** Worker 使用不同于 Task owner 的主体读取快照
- **THEN** Attachment Port 拒绝读取
- **AND** Task 按不可重试输入失败结束且不泄漏文件信息

### Requirement: 固定 Tender Executor 必须遵守 Worker lease 和取消边界

系统 MUST 通过服务端固定 task type 到 Tender Executor 的绑定执行任务。Executor MUST 只通过 `TaskExecutionContext` 取得 task_id、owner、快照引用和取消/续租回调，不得访问 Task Repository 或直接修改 Task 状态；结果必须通过 Worker 的成功/失败命令回写。

#### Scenario: Worker 成功执行 Tender 任务

- **WHEN** Worker 领取有效 `tender.generate_bid_skeleton` Task，且快照可读、TenderApplication 返回已验证结果
- **THEN** Executor 保存内部结果副本并返回安全结果指纹和有限摘要
- **AND** Worker 将 Task 转为 `succeeded` 并记录安全完成事件

#### Scenario: 未登记 task type 不执行

- **WHEN** Worker 领取未知或未绑定的 task type
- **THEN** Worker 返回固定 `EXECUTOR_UNAVAILABLE` 失败
- **AND** 不调用 TenderApplication 或任意动态导入目标

#### Scenario: 执行期间收到取消请求

- **WHEN** Task 状态变为 `cancel_requested` 且 Executor 到达取消检查点
- **THEN** Executor 停止后续 Tender 调用并返回取消结果
- **AND** Worker 通过既有协作取消命令将 Task 转为 `cancelled`

### Requirement: Tender 失败必须按安全分类进入既有重试状态机

系统 MUST 将 Tender 输入无效、附件不可用、结果契约无效和配置缺失映射为不可重试安全错误；上游服务暂时失败 MUST 映射为可重试错误并提供固定退避时间。原始异常、输入内容和模型响应不得进入 Task Event、结果摘要或公开状态。

#### Scenario: 上游暂时失败

- **WHEN** TenderApplication 抛出受控上游服务错误且尝试次数未耗尽
- **THEN** Executor 返回 transient failure 和固定 `retry_at`
- **AND** Worker 将 Task 转为 `retry_wait`，后续由 RetryScheduler 重入队

#### Scenario: 输入或配置失败

- **WHEN** 快照缺失、文档解析失败、分析结果无效或模型配置缺失
- **THEN** Executor 返回不可重试安全失败码
- **AND** Task 转为 `failed` 且事件不包含底层异常原文

#### Scenario: 失败结果不泄漏敏感数据

- **WHEN** Tender 执行失败
- **THEN** Task 摘要和事件只包含固定分类、失败码和尝试序号
- **AND** 不包含附件内容、快照正文、lease token、Prompt 或 Provider 响应

### Requirement: Tender 异步链路必须保持主体隔离和幂等

系统 MUST 以可信主体读取输入快照和写入结果；同一主体、能力和 call_id 的重放 MUST 返回同一 Task 引用，不得重复创建 Task 或结果回执。不同主体不得读取、取消、重试或执行另一主体的 Tender Task。

#### Scenario: 相同调用重放

- **WHEN** 同一主体以相同能力、call_id 和输入指纹重复提交
- **THEN** 系统返回原 Task execution reference
- **AND** 不创建第二个 Task、Attempt 或初始事件

#### Scenario: 主体查询隔离

- **WHEN** 另一主体通过既有 Task 管理接口查询、取消或重试该 Tender Task
- **THEN** 系统返回主体隔离的未找到或拒绝结果
- **AND** 原 Task 状态、事件和结果保持不变

### Requirement: 异步 Tender 只能从内部绑定触发

系统 MUST 不新增通用 Task 创建、领取、续租、结果回写或 Executor 注册的 HTTP、MCP、Function Calling 和浏览器入口。Tender 路由、快照适配器、结果存储和 Worker 必须由 Composition Root 固定组装。

#### Scenario: 检查公开接口边界

- **WHEN** 调用方检查现有 HTTP、MCP 和浏览器接口
- **THEN** 只能看到既有 Task 查询、取消和手动重试能力
- **AND** 不能提交任意 Tender 输入快照、Task 类型或 Executor 地址

#### Scenario: 默认配置不改变同步系统

- **WHEN** Tender 异步路由未配置或快照依赖不可用
- **THEN** 未登记异步能力继续同步执行，登记能力返回受控不可用错误
- **AND** 不发生隐式同步降级或公开 Task 创建

