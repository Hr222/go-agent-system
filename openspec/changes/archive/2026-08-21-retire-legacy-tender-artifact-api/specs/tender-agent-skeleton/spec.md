## ADDED Requirements

### Requirement: 浏览器 Tender 请求必须经过受控对话调用

浏览器 MUST 通过已授权的 Interaction、显式确认和 Dialogue Agent Invocation 发起 Tender 骨架生成。系统 MUST NOT 保留一个能直接执行 Tender Application 的浏览器同步 HTTP 入口。

#### Scenario: 浏览器使用旧同步生成地址
- **WHEN** 浏览器请求 `POST /api/v1/agents/tender/skeleton`
- **THEN** 系统返回路由不存在响应
- **AND** 系统不读取上传文件、不调用 Tender Application，也不生成文件资源

#### Scenario: 用户从 Tender 页面发起生成
- **WHEN** 用户访问 `/agents/tender` 并选择发起生成
- **THEN** 页面进入 `/chat`
- **AND** 后续文件上传、能力确认、Agent 调用和结果下载使用现有受控对话链路
- **AND** 页面不发送原始文件或 Base64 内容到旧 Tender 同步地址
