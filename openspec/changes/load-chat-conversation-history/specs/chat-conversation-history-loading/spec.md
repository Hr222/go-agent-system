## ADDED Requirements

### Requirement: Chat 加载当前 Conversation 的持久化消息

Chat 前端 MUST 在存在当前 `conversation_id` 时调用历史 API，按服务端 sequence 顺序显示 Message。分页加载不得重复或重排消息。

#### Scenario: 页面恢复已有会话

- **WHEN** 页面初始化时恢复一个有效当前 Conversation 标识
- **THEN** Chat 显示服务端返回的有序历史消息
- **AND** 不伪造本地欢迎消息替代持久化历史

#### Scenario: 历史跨多页

- **WHEN** 会话消息超过单页上限
- **THEN** 页面可以请求后续游标页
- **AND** 已显示消息与新页消息不重复且保持 sequence 顺序

### Requirement: 历史加载失败具有可恢复状态

Chat MUST 展示加载中、空会话和网络失败状态。会话不存在或访问未准入时 MUST 清除当前选择；可重试网络失败 MUST 保留当前选择并允许重试。

#### Scenario: 保存的会话不可访问

- **WHEN** 历史 API 返回会话不存在或受控拒绝
- **THEN** Chat 清除当前 Conversation 标识
- **AND** 不显示该会话的缓存消息
