## Why

后续多个 Agent 都可能需要图片或文档。若每个 Agent 各自实现文件选择和上传状态，前端会重复处理错误、重试和引用传递。需要一个不绑定业务的附件交互组件。

## What Changes

- 提供通用文件选择、上传、进度和失败重试组件。
- 组件输出不透明附件引用，不直接把文件内容放入聊天文本。
- 保持当前纯文本聊天流程兼容。

## Capabilities

### New Capabilities

- `frontend-attachment-component`: 可复用的前端附件选择和上传交互。

### Modified Capabilities

- 无。

## Impact

影响 React/TypeScript 前端组件、上传 API 客户端和聊天输入状态；不改变后端 Agent 执行逻辑。
