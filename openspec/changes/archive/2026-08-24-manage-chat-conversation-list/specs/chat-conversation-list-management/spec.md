## ADDED Requirements

### Requirement: Chat 侧栏展示当前主体的会话摘要

Chat 前端 MUST 使用会话摘要 API 展示当前主体可访问的 Conversation，按服务端返回顺序渲染。页面 MUST 覆盖加载、空列表、失败与显式重试状态。

#### Scenario: 加载会话侧栏

- **WHEN** 当前主体拥有 Conversation
- **THEN** 侧栏展示其摘要而不展示其他主体的会话
- **AND** 顺序与服务端摘要列表一致

#### Scenario: 列表为空

- **WHEN** 当前主体没有 Conversation
- **THEN** 侧栏显示空状态
- **AND** 用户仍可使用新建对话操作

### Requirement: 用户可以新建和切换当前会话

Chat MUST 在用户选择摘要时更新当前 Conversation 标识并触发既有历史加载。新建对话 MUST 调用创建接口获得服务器生成的会话标识，而不是在浏览器生成 UUID。

#### Scenario: 选择历史会话

- **WHEN** 用户选择一个会话摘要
- **THEN** Chat 将其设为当前 Conversation
- **AND** 页面加载并显示该会话历史

#### Scenario: 新建会话

- **WHEN** 用户点击新建对话
- **THEN** Chat 调用创建接口并选择返回的空 Conversation
- **AND** 侧栏刷新后包含该 Conversation
