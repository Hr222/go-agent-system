## Context

当前会话标识可以由浏览器保存，历史 HTTP API 可以返回分页消息。Chat 需要独立处理其加载生命周期。

## Goals / Non-Goals

**Goals:** 恢复当前会话的真实 Message，支持从最早页连续加载，覆盖 loading/empty/error/denied。

**Non-Goals:** 不实现列表、搜索、标题、上下文构建或消息写入。

## Decisions

- React Query 管理历史页面；页面只把 HTTP Message 映射到可展示的 ChatMessage。
- 切换/刷新时取消过期请求，避免旧会话响应覆盖新选择。
- 被拒绝或不存在时清除 active ID；普通网络错误保留选择并提供重试。

## Risks / Trade-offs

- [历史 event 不在消息页中] → Agent 历史时间线投影留待独立 Change，不把事件伪装成普通消息。
