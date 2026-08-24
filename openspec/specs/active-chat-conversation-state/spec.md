## Purpose

为 Chat 保存当前有效 Conversation 标识，支持刷新恢复并在选择失效时清除本地状态。

## Requirements

### Requirement: Chat 保存当前 Conversation 标识

Chat 前端 MUST 在浏览器本地保存服务端返回或用户选择的有效 `conversation_id`，并在页面初始化时恢复它。前端 MUST NOT 生成或猜测 Conversation UUID。

#### Scenario: 服务端返回新会话标识

- **WHEN** 创建接口或普通 Chat 元数据返回有效 `conversation_id`
- **THEN** Chat 将该标识保存为当前 Conversation
- **AND** 后续相关请求使用该标识

#### Scenario: 刷新页面

- **WHEN** 用户刷新有已保存 Conversation 标识的 Chat 页面
- **THEN** 页面恢复该标识为当前选择
- **AND** 不创建新的 Conversation

### Requirement: 无效当前会话选择被清除

Chat MUST 在用户选择新对话，或历史查询报告会话不存在/未准入时清除本地当前 `conversation_id`。

#### Scenario: 历史访问被拒绝

- **WHEN** 已保存的 Conversation 标识不能被当前请求主体读取
- **THEN** Chat 清除该标识
- **AND** 页面回到无当前会话状态
