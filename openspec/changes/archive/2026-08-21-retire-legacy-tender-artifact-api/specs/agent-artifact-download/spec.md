## ADDED Requirements

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
