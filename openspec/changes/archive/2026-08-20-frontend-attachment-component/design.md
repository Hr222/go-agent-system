## Context

当前聊天输入主要传递文本和 `provided_inputs`。通用附件组件应负责动态引用的生命周期显示，而不是理解 Tender 或图片 Agent 的业务字段。

## Goals / Non-Goals

**Goals:**

- 用户可选择、上传、查看进度、重试和移除附件。
- 聊天请求只携带附件引用和安全元数据。

**Non-Goals:**

- 不实现具体 Agent 的附件字段映射。
- 不在前端解析、Base64 编码或持久化完整文件内容。

## Decisions

- 复用现有 React/TypeScript 和 HTTP 客户端约定，以受控组件暴露 `AttachmentRef`。
- 上传失败、过期和取消均为显式状态；纯文本提交不受影响。
- 不使用静态附件 ID，浏览器验收必须观察服务端动态引用。

## Risks / Trade-offs

- [组件与聊天状态耦合] -> 只输出引用列表和状态，业务页面决定何时提交。
- [大文件重复上传] -> 显示进度和失败重试，后端仍是最终大小校验者。

## Migration Plan

组件先以独立示例和测试接入，不修改现有聊天默认路径；Tender 绑定由后续 Adapter Change 完成。

## Open Questions

断点续传不是当前范围，后续按真实文件规模评估。
