## MODIFIED Requirements

### Requirement: 已完成 Agent 的文件产物必须拥有受控资源

系统 MUST 在同步 Agent 或异步 Task 成功返回包含文件字节的产物后，将每个产物完整暂存为服务端生成的资源，并在安全结果摘要或 Task 资源清单中保存资源 ID、文件名、媒体类型和字节大小。系统 MUST NOT 将文件字节、本地路径、Provider 原始响应或执行器对象写入 Conversation 事件、Task 事件、续写上下文或 HTTP JSON 响应。

#### Scenario: Agent 成功生成一个或多个文件

- **WHEN** 已授权的同步 Agent 或受信任异步 Task 返回带有文件名、媒体类型和非空字节内容的一个或多个产物
- **THEN** 系统为每个产物生成可下载资源并校验完整写入
- **AND** 安全结果包含每个资源的元数据和资源 ID
- **AND** Conversation/Task 事件不包含原始文件字节或物理路径

#### Scenario: 产物暂存失败

- **WHEN** Agent 或异步 Task 返回文件后任一产物无法被完整暂存或校验
- **THEN** 系统删除该次调用已经暂存的产物
- **AND** 同步调用返回 `AGENT_ARTIFACT_STORE_FAILED` 或异步 Task 返回 `TENDER_RESULT_RESOURCE_STORE_FAILED` 受控失败
- **AND** 不写入包含无效资源 ID 的成功结果事件或资源清单
