## Context

Tender V1 Application 接受 `TenderGenerateSkeletonCommand(file_name, content)`，平台目录目前以 Base64 表示输入。附件适配器应在服务端读取引用并构造该命令，避免把二进制内容交给 LLM 或客户端。

## Goals / Non-Goals

**Goals:**

- 通过通用附件引用触发 Tender 的输入校验和确认流程。
- 保持 DOCX、大小和解析错误由 Tender 现有边界处理。

**Non-Goals:**

- 不改变 Tender 分块、LLM 或渲染逻辑。
- 不让 Tender Adapter 直接访问数据库或具体文件系统。

## Decisions

- Adapter 依赖 Attachment Access/Resolution Port 和 Tender Application Port。
- 只接受能力声明允许的 DOCX 附件；读取后生成请求级不可变内容。
- 对话事件、确认卡和 LLM 上下文只保存附件元数据和产物引用，不保存 Base64。

## Risks / Trade-offs

- [大文件内存压力] -> 复用 Tender 现有大小限制，并在更大文件场景由后续流式能力单独设计。
- [旧 Base64 客户端兼容] -> 适配器先支持引用路径，旧同步 Tender HTTP 入口保持独立。

## Migration Plan

先在 Interaction Chat 路径启用附件引用；现有 `/tender/skeleton` 同步上传接口不在本 Change 内删除。

## Open Questions

附件产物下载引用的统一格式由后续文件产出 Change 决定。
