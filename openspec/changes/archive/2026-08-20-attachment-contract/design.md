## Context

仓库已有面向政策入库的 `UploadStoragePort`，但其 `StagedUpload` 暴露 `stored_path`，且契约与政策流程绑定。附件契约需要隐藏路径并允许不同 Agent 读取同一类引用。

## Goals / Non-Goals

**Goals:**

- 定义不透明、可序列化的附件引用。
- 提供读取元数据和二进制内容的端口边界。

**Non-Goals:**

- 不实现文件系统存储、HTTP 上传或前端控件。
- 不规定每个 Agent 的业务输入字段。

## Decisions

- 引用使用随机 `attachment_id`，不允许客户端传路径。
- 元数据包含文件名、媒体类型、大小、哈希和状态，内容通过 Port 读取。
- 保留现有政策 Port 的兼容性，后续以 Adapter 接入通用契约而不是一次性破坏旧接口。

## Risks / Trade-offs

- [契约过宽] -> 只保留通用文件元数据和读取操作，业务字段由能力适配器定义。
- [事件泄漏敏感信息] -> 规范中禁止写入完整内容和服务器路径。

## Migration Plan

先新增契约，不迁移现有调用方；后续存储 Change 提供兼容适配器。

## Open Questions

附件是否允许多次读取由访问绑定 Change 决定。

