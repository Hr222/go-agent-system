## Purpose

定义 Agent 生成文件的临时资源生命周期、主体与会话访问约束、后端重启恢复规则和浏览器受控下载契约。

## Requirements

### Requirement: 浏览器 Agent 文件不得由旧同步 JSON 交付

浏览器获得 Tender Agent 生成文件时，系统 MUST 仅返回受控资源摘要并通过受主体与会话约束的下载接口交付文件内容。系统 MUST NOT 通过旧 Tender 同步 HTTP JSON 响应返回文件 Base64 内容。

#### Scenario: 已授权 Tender 调用生成文件

- **WHEN** 用户在受控对话中确认 Tender Agent 调用并成功生成文件
- **THEN** 响应和 Conversation 事件只包含资源 ID、文件名、媒体类型和大小等安全元数据
- **AND** 浏览器使用下载接口取得文件内容

#### Scenario: 浏览器尝试接收旧 Base64 文件响应

- **WHEN** 浏览器请求已退场的旧 Tender 同步生成地址
- **THEN** 系统不返回任何文件内容或 Base64 字段
- **AND** 系统不创建可绕过对话访问约束的文件资源

### Requirement: 已完成 Agent 的文件产物必须拥有受控资源

系统 MUST 在 Agent 成功返回包含文件字节的产物后，将每个产物完整暂存为服务端生成的资源，并在安全结果摘要中保存资源 ID、文件名、媒体类型和字节大小。系统 MUST NOT 将文件字节、本地路径、Provider 原始响应或执行器对象写入 Conversation 事件、续写上下文或 HTTP JSON 响应。

#### Scenario: Agent 成功生成一个或多个文件
- **WHEN** 已授权的 Agent 返回带有文件名、媒体类型和非空字节内容的一个或多个产物
- **THEN** 系统为每个产物生成可下载资源并校验完整写入
- **AND** 结果摘要包含每个资源的安全元数据和资源 ID
- **AND** Conversation 事件不包含原始文件字节或物理路径

#### Scenario: 产物暂存失败
- **WHEN** Agent 返回文件后任一产物无法被完整暂存或校验
- **THEN** 系统删除该次调用已经暂存的产物
- **AND** 返回 `AGENT_ARTIFACT_STORE_FAILED` 受控失败
- **AND** 不写入包含无效资源 ID 的成功结果事件

### Requirement: Agent 产物下载必须受主体和会话约束

系统 MUST 仅向与生成调用的主体和 Conversation 均匹配的请求返回未过期的 Agent 产物。下载接口 MUST 以附件资源 ID 和 Conversation ID 定位资源，并以附件形式返回原始媒体类型和安全文件名。

#### Scenario: 所有权匹配时下载成功
- **WHEN** 当前主体使用生成该产物的 Conversation ID 请求可用资源
- **THEN** 系统返回文件内容、原始媒体类型和 `Content-Disposition: attachment`
- **AND** 响应不暴露服务端物理路径或内部执行信息

#### Scenario: 主体、会话或资源状态不匹配
- **WHEN** 请求的资源不存在、已过期、已消费，或当前主体与 Conversation 任一项不匹配
- **THEN** 系统返回受控的不可用响应
- **AND** 响应不区分资源不存在与无权访问

### Requirement: 临时资源在后端重启后保持访问约束

系统 MUST 将临时资源的引用、主体、会话、校验信息和到期时间与文件一同保存，并在后端重启后恢复仍在保留期内的记录。系统 MUST 清理无效、过期或缺少完整元数据的临时目录。

#### Scenario: 重启后下载仍在保留期内的产物
- **WHEN** 服务端重启后，用户请求尚未过期且文件校验仍正确的 Agent 产物
- **THEN** 系统恢复资源访问记录
- **AND** 匹配主体和 Conversation 的请求仍可下载该文件

#### Scenario: 恢复时发现不完整目录
- **WHEN** 服务端初始化时发现缺少有效元数据清单或文件校验失败的临时资源目录
- **THEN** 系统不恢复该资源
- **AND** 清理该目录或将其作为不可用资源处理
