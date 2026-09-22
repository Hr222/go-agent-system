# task-result-resources Specification

## Purpose

定义已完成 Task 结果资源的主体隔离、Conversation 绑定、完整性校验和受控下载投影。

## Requirements

### Requirement: 已完成 Task 必须安全投影结果资源

系统 MUST 只为成功且具备受信任 Conversation 绑定的 Task 返回结果资源清单。资源清单 MUST 只包含 opaque resource ID、文件名、媒体类型、大小、哈希和服务端生成下载 URL，不得包含物理路径、内部结果 JSON、输入附件、Prompt、Provider 响应或凭据。

#### Scenario: 主体读取成功任务的资源
- **WHEN** 已认证主体读取自己成功且已绑定 Conversation 的 Tender Task 资源
- **THEN** 系统返回经过完整性验证的安全资源元数据和下载 URL

#### Scenario: 任务未成功或没有 Conversation 绑定
- **WHEN** Task 不是 succeeded 或缺少受信任 Conversation 绑定
- **THEN** 系统返回统一的资源不可用结果
- **AND** 不泄漏 Task 是否有内部结果或其他主体资源

#### Scenario: 资源已过期或损坏
- **WHEN** 资源 manifest、Attachment 生命周期或内容校验不再有效
- **THEN** 系统返回统一的资源不可用结果
- **AND** 不返回部分资源或底层存储错误

### Requirement: Tender 结果资源必须原子地绑定主体和 Conversation

Tender Executor MUST 在 Task 成功前保存可交付文件资源，并将每个资源与 Task owner 和 Conversation 绑定。重复保存 MUST 只在 Task、owner、Conversation 和资源元数据一致时复用已有资源。

#### Scenario: 保存会话绑定的 Tender 产物
- **WHEN** TenderApplication 产生有效交付文件且 Task 具有 Conversation 绑定
- **THEN** 系统将文件存入 Attachment 存储、写入 Task 资源 manifest，并返回安全结果摘要

#### Scenario: 资源保存部分失败
- **WHEN** 任一结果文件或 manifest 保存失败
- **THEN** 系统清理本次创建的资源并以固定不可重试失败码结束 Task
- **AND** 不将 Task 标记为 succeeded

#### Scenario: 重复执行的绑定不一致
- **WHEN** 相同 Task 的既有资源 manifest 对应不同主体、Conversation 或文件元数据
- **THEN** 系统拒绝复用并以受控错误结束本次执行
