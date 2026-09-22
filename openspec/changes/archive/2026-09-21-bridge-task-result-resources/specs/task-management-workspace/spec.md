## ADDED Requirements

### Requirement: 成功任务详情必须展示结果资源

任务详情页 MUST 对成功 Task 查询服务端结果资源清单，并展示文件名、媒体类型、大小和下载入口。页面不得自行拼接资源 ID、Conversation ID 或存储路径。

#### Scenario: 展示可下载资源
- **WHEN** 成功 Task 的资源清单查询返回一个或多个资源
- **THEN** 页面展示每个资源的安全元数据和服务端提供的下载 URL

#### Scenario: 资源不可用
- **WHEN** 服务端返回资源不可用或资源列表为空
- **THEN** 页面显示受控资源不可用状态，不伪造下载文件或结果内容
