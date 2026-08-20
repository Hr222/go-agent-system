# attachment-contract Specification

## Purpose
Define the reusable opaque attachment reference and content-read contract for
HTTP clients and capability adapters.
## Requirements
### Requirement: 不透明附件引用

系统 MUST 使用服务端生成的 `attachment_id` 表示附件，并为调用方提供文件名、媒体类型、大小、哈希和生命周期状态等元数据；不得把服务器路径或完整内容作为引用返回。

#### Scenario: 创建附件引用
- **WHEN** 文件被接受并生成附件引用
- **THEN** 返回非空且不可由原始路径推导的 `attachment_id`
- **AND** 返回必要的安全元数据

#### Scenario: 附件内容通过 Port 读取
- **WHEN** 应用层持有合法附件引用并请求内容
- **THEN** 通过附件读取 Port 获取内容
- **AND** 应用层不需要知道物理存储路径

### Requirement: 引用状态可观察

系统 MUST 为附件区分可用、已消费、过期和不存在等状态。

#### Scenario: 已过期引用
- **WHEN** 应用层读取已过期附件
- **THEN** 返回稳定的不可用结果
- **AND** 不返回文件内容
