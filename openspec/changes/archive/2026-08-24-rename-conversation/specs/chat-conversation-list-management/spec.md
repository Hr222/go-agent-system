## MODIFIED Requirements

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
