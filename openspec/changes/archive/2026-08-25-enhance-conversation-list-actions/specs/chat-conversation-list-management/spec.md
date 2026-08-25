## MODIFIED Requirements

### Requirement: Chat 侧栏展示当前主体的会话摘要

Chat 前端 MUST 使用会话摘要 API 展示当前主体可访问的 Conversation，优先展示持久化的 `topic_summary`，缺少话题概括时回退为日期标题，并显示置顶状态。页面 MUST 覆盖加载、空列表、失败与显式重试状态。

#### Scenario: 加载会话侧栏

- **WHEN** 当前主体拥有 Conversation
- **THEN** 侧栏展示其摘要而不展示其他主体的会话
- **AND** 顺序与服务端返回顺序一致
- **AND** 置顶会话有可识别的置顶状态

#### Scenario: 列表为空

- **WHEN** 当前主体没有 Conversation
- **THEN** 侧栏显示空状态
- **AND** 用户仍可使用新建对话操作

#### Scenario: 缺少话题概括时回退

- **WHEN** 会话摘要的 `topic_summary` 为空
- **THEN** 侧栏使用稳定的日期回退标题

### Requirement: 用户可以新建、切换和编辑当前会话

Chat MUST 在用户选择摘要时更新当前 Conversation 标识并触发既有历史加载。新建对话 MUST 调用创建接口获得服务器生成的会话标识，而不是在浏览器生成 UUID。用户 MUST 可以通过会话菜单编辑当前主体会话的话题概括并保存或清除。

#### Scenario: 选择历史会话

- **WHEN** 用户选择一个会话摘要
- **THEN** Chat 将其设为当前 Conversation
- **AND** 页面加载并显示该会话历史

#### Scenario: 新建会话

- **WHEN** 用户点击新建对话
- **THEN** Chat 调用创建接口并选择返回的空 Conversation
- **AND** 侧栏刷新后包含该 Conversation

#### Scenario: 手动修改话题概括

- **WHEN** 用户从会话菜单选择重命名并提交新的话题概括
- **THEN** Chat 调用当前主体范围的更新接口
- **AND** 侧栏显示保存后的话题概括

#### Scenario: 保存失败

- **WHEN** 话题概括更新接口失败
- **THEN** Chat 保留用户正在编辑的内容并显示可重试状态
- **AND** 不覆盖服务端已有话题概括
