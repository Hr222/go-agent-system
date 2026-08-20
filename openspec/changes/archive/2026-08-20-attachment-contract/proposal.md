## Why

当前 Chat 能力把文件内容作为客户端提交的 `content_base64`，无法安全、可复用地支持后续图片或文档 Agent。需要先定义与具体业务无关的不透明附件引用契约。

## What Changes

- 定义 `AttachmentRef` 元数据契约和附件读取 Port。
- 附件引用只包含服务端生成的 ID，不暴露存储路径或原始内容。
- 明确附件状态、文件名、媒体类型、大小和摘要信息。

## Capabilities

### New Capabilities

- `attachment-contract`: 跨 Agent 复用的附件引用与读取契约。

### Modified Capabilities

- 无。

## Impact

新增通用模块契约；不改变现有政策上传接口、Tender HTTP 接口或数据库。

