## ADDED Requirements

### Requirement: 通用 multipart 附件上传

系统 MUST 接受合法 multipart 文件并返回服务端生成的附件引用及安全元数据；上传接口 MUST 不启动业务能力。

#### Scenario: 上传成功
- **WHEN** 客户端提交非空且类型、大小合法的文件
- **THEN** HTTP 返回成功状态和动态 `attachment_id`
- **AND** 响应不包含服务器路径或完整文件内容

#### Scenario: 上传输入无效
- **WHEN** 文件为空、类型不允许或超过大小限制
- **THEN** HTTP 返回稳定的客户端错误
- **AND** 不留下可读取的附件

#### Scenario: 上传不触发 Agent
- **WHEN** 上传接口成功返回附件引用
- **THEN** Tender、LLM 和其他 Agent 均未被调用

