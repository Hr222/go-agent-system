## Context

前端需要在页面刷新后知道当前会话，但此 Change 不负责加载消息。

## Goals / Non-Goals

**Goals:** 将服务器产生或用户选择的 UUID 保存在浏览器本地，提供明确清除时机。

**Non-Goals:** 不生成 UUID、不调用历史 API、不管理会话侧栏。

## Decisions

- 使用 versioned `localStorage` 键保存单个 UUID，React hook 负责读取、校验、写入和清除。
- 当创建成功、普通 Chat `meta` 或用户切换产生新 ID 时更新；新建、历史 404/拒绝时清除。
- 无效值当作未选择状态，不能传给 API。

## Risks / Trade-offs

- [共享浏览器残留选择] → 未来认证 Change 以 subject 命名空间隔离键；当前静态 Mock 环境接受单键。
