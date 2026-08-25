## Purpose

定义 Chat 侧栏的会话摘要展示、当前会话切换、服务端创建会话以及话题概括维护契约，覆盖前端可恢复的常见状态。

## Requirements

### Requirement: Chat 侧栏展示当前主体的会话摘要

Chat 前端 MUST 使用会话摘要 API 展示当前主体可访问的 Conversation，优先展示持久化的 `topic_summary`，缺少话题概括时回退为日期标题，并显示置顶状态。页面 MUST 覆盖加载、空列表、失败与显式重试状态。

#### Scenario: 加载会话侧栏

- **WHEN** 当前主体拥有 Conversation
- **THEN** 侧栏展示其摘要而不展示其他主体的会话
- **AND** 顺序与服务端摘要列表一致
- **AND** 置顶会话有可识别的置顶状态

#### Scenario: 列表为空

- **WHEN** 当前主体没有 Conversation
- **THEN** 侧栏显示空状态
- **AND** 用户仍可使用新建对话操作

#### Scenario: 缺少话题概括时回退

- **WHEN** 会话摘要的 `topic_summary` 为空
- **THEN** 侧栏使用稳定的日期回退标题

### Requirement: 用户可以新建、切换和编辑当前会话

Chat MUST 在用户选择摘要时更新当前 Conversation 标识并触发既有历史加载。新建对话 MUST 调用创建接口获得服务器生成的会话标识，而不是在浏览器生成 UUID。用户 MUST 可以通过会话菜单编辑当前主体会话的话题概括并保存或清除，且菜单与编辑操作不得触发会话切换。

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

#### Scenario: 清除话题概括

- **WHEN** 用户清空重命名输入并保存
- **THEN** Chat 调用更新接口提交空话题概括
- **AND** 侧栏回退为日期标题

#### Scenario: 保存失败

- **WHEN** 话题概括更新接口失败
- **THEN** Chat 保留用户正在编辑的内容并显示可重试状态
- **AND** 不覆盖服务端已有话题概括

### Requirement: Chat 支持单项删除确认

Chat MUST 在单个会话删除请求前展示二次确认。确认前不得发送删除请求。删除当前会话成功后页面 MUST 清理当前会话、消息和编辑状态；删除失败时 MUST 保留会话并显示失败提示。

#### Scenario: 删除前确认

- **WHEN** 用户从会话菜单选择删除
- **THEN** 页面展示待删除会话和确认、取消操作
- **AND** 用户取消时不发送删除请求

#### Scenario: 删除成功

- **WHEN** 用户确认删除且删除请求成功
- **THEN** 页面刷新会话列表并显示成功反馈
- **AND** 若目标是当前会话则清空消息和当前会话状态

#### Scenario: 删除失败

- **WHEN** 删除请求失败
- **THEN** 页面保留目标会话
- **AND** 页面显示失败提示，不假报删除成功
