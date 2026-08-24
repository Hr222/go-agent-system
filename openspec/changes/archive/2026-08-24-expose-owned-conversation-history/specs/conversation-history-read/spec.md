## MODIFIED Requirements

### Requirement: 历史读取保持只读和模块边界

历史读取 MUST 只通过 Conversation 读取应用服务和 Port 查询，不得修改 Conversation/Message 或调用 LLM、Agent。系统可以在 Conversation Access 主体校验通过后，通过专用 HTTP 查询适配器向浏览器返回消息历史页；该适配器不得绕过应用服务或把 HTTP Schema 传入 Domain。

#### Scenario: 历史读取期间追加新消息

- **WHEN** 读取一页历史的同时另一个请求向同一会话追加消息
- **THEN** 已返回页面保持 `sequence` 升序
- **AND** 调用方可以使用返回游标继续读取之后的消息
- **AND** 历史读取不阻塞或修改追加事务

#### Scenario: 当前主体通过 HTTP 读取历史

- **WHEN** 当前主体经 Conversation Access 校验后请求自己的历史消息页
- **THEN** HTTP 适配器返回应用服务读取的有序消息页
- **AND** 系统不调用 LLM 或 Agent，也不修改会话
