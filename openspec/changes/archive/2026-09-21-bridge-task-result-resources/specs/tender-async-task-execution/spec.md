## MODIFIED Requirements

### Requirement: 固定 Tender Executor 必须遵守 Worker lease 和取消边界

系统 MUST 通过服务端固定 task type 到 Tender Executor 的绑定执行任务。Executor MUST 只通过 `TaskExecutionContext` 取得 task_id、owner、快照引用和取消/续租回调，不得访问 Task Repository 或直接修改 Task 状态；结果必须通过 Worker 的成功/失败命令回写。对于具有受信任 Conversation 绑定的成功结果，Executor MUST 在成功回写前将可交付文件保存为 owner/Conversation 绑定的结果资源。

#### Scenario: Worker 成功执行 Tender 任务

- **WHEN** Worker 领取有效 `tender.generate_bid_skeleton` Task，且快照可读、TenderApplication 返回已验证结果
- **THEN** Executor 保存内部结果副本和会话绑定的可交付资源，并返回安全结果指纹和有限摘要
- **AND** Worker 将 Task 转为 `succeeded` 并记录安全完成事件

#### Scenario: 未登记 task type 不执行

- **WHEN** Worker 领取未知或未绑定的 task type
- **THEN** Worker 返回固定 `EXECUTOR_UNAVAILABLE` 失败
- **AND** 不调用 TenderApplication 或任意动态导入目标

#### Scenario: 执行期间收到取消请求

- **WHEN** Task 状态变为 `cancel_requested` 且 Executor 到达取消检查点
- **THEN** Executor 停止后续 Tender 调用并返回取消结果
- **AND** Worker 通过既有协作取消命令将 Task 转为 `cancelled`
