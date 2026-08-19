## MODIFIED Requirements

### Requirement: V2 对话入口不暴露内部授权字段

系统 MUST 仅通过正常 Chat 对话入口发起 Agent 调用。请求接受用户自然语言、可选 Conversation 标识和附件等原始上下文；能力代码、权限、分发键、执行器地址、批准对象和调用标识必须由服务端的 Gateway、目录、主体解析和 Dialogue 应用服务生成。Gateway 必须校验原始上下文后才生成业务输入。系统 MUST NOT 提供独立的浏览器 Agent 调用 HTTP 入口。

#### Scenario: Chat 中创建新会话并提交自然语言

- **WHEN** 页面未提供会话标识并提交自然语言，且 Gateway 识别为需要确认的 Agent 能力
- **THEN** 系统创建 Conversation、生成调用 ID 并返回会话标识及待确认状态
- **AND** 页面只能通过提议标识确认或取消该调用

#### Scenario: 客户端试图直接发起 Agent 调用

- **WHEN** 浏览器请求已移除的独立 Agent 调用地址，或提交能力代码、权限、分发键、执行器 URL、调用 ID 或伪造批准对象
- **THEN** 系统不提供执行路径或不使用这些字段授予执行权限
- **AND** 客户端必须改由 Chat 的自然语言与确认提议完成调用
