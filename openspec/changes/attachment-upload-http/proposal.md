## Why

通用附件存储完成后，Agent 仍缺少一个不绑定业务的 HTTP 上传入口。需要让浏览器或其他客户端上传文件并获得动态附件引用，而不是把 Base64 直接放入聊天请求。

## What Changes

- 增加通用 multipart 文件上传接口。
- 返回附件引用和安全元数据，不返回服务器路径或完整内容。
- 映射大小、类型和空文件错误为稳定 HTTP 响应。

## Capabilities

### New Capabilities

- `attachment-upload-http`: 通过 HTTP 创建通用附件引用。

### Modified Capabilities

- 无。

## Impact

新增 HTTP 路由、Schema 和依赖注入；不调用 Agent、不创建对话事件，不修改现有政策上传路由。

