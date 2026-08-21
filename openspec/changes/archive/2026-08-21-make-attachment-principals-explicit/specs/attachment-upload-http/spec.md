## MODIFIED Requirements

### Requirement: 通用 multipart 附件上传

系统 MUST 接受由具有可信主体的请求提交的合法 multipart 文件，并返回服务端生成的附件引用及安全元数据；上传接口 MUST 不启动业务能力。主体缺失时，系统 MUST 拒绝上传而不创建附件引用。

#### Scenario: 上传成功

- **WHEN** 具有可信主体的客户端提交非空且类型、大小合法的文件
- **THEN** HTTP 返回成功状态和动态 `attachment_id`
- **AND** 响应不包含服务器路径或完整文件内容

#### Scenario: 上传输入无效

- **WHEN** 文件为空、类型不允许或超过大小限制
- **THEN** HTTP 返回稳定的客户端错误
- **AND** 不留下可读取的附件

#### Scenario: 上传不触发 Agent

- **WHEN** 上传接口成功返回附件引用
- **THEN** Tender、LLM 和其他 Agent 均未被调用

#### Scenario: 匿名请求上传附件

- **WHEN** 请求主体没有可信主体标识
- **THEN** HTTP 返回 `403` 和错误码 `ATTACHMENT_PRINCIPAL_REQUIRED`
- **AND** 系统不调用附件存储或业务能力
- **AND** 系统不返回 `attachment_id`
