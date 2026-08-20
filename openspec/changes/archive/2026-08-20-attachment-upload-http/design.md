## Context

项目已有面向政策流水线的 multipart 路由，但它在上传后立即运行政策用例。通用附件上传必须只负责暂存并返回引用，后续能力消费由独立解析 Change 负责。

## Goals / Non-Goals

**Goals:**

- 提供可被不同 Agent 复用的上传入口。
- 使用 TestClient 和真实临时存储验证动态响应。

**Non-Goals:**

- 不绑定 Tender 或政策业务。
- 不在上传请求中调用 LLM 或 Agent。

## Decisions

- 使用 multipart `UploadFile`，由存储 Port 处理流式写入。
- 响应只包含 `attachment_id`、文件名、媒体类型、大小和哈希等元数据。
- 失败响应不包含路径、完整输入或底层堆栈。

## Risks / Trade-offs

- [大文件占用请求资源] -> 流式写入并复用存储层大小上限。
- [上传后无人消费] -> 由附件 TTL 清理 Change 负责，不在路由内同步处理业务。

## Migration Plan

新增独立路由，不修改已有政策上传 URL；可按配置逐步开放。

## Open Questions

附件与主体绑定由下一个访问控制 Change 完成。

