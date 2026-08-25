## Context

Chat 侧栏已支持在会话项内联重命名。当前保存成功后通过 `listActionNotice` 写入侧栏共享状态区；该区域也承担置顶和删除的成功反馈。重命名是一次完成即结束的局部操作，持续占用侧栏空间会干扰后续会话浏览。

## Goals / Non-Goals

**Goals:**

- 在重命名成功时调用现有 Ant Design `message.success` 显示短暂的全局成功提示。
- 保持保存成功后的编辑器关闭、草稿清理和会话列表刷新行为。
- 通过组件测试锁定成功提示出口，避免以后重新写入侧栏状态区。

**Non-Goals:**

- 不改变话题概括更新接口、React Query mutation、持久化或权限校验。
- 不迁移置顶和删除的侧栏反馈。
- 不改变重命名失败时在目标会话项内保留草稿和错误的行为。

## Decisions

### 在重命名成功分支直接使用 `message.success`

现有页面已使用 Ant Design `message.error` 处理置顶和删除失败，因此直接在 `saveRename` 成功分支调用 `message.success("会话名称已更新")`，不新增通知状态、组件或依赖。相较复用 `listActionNotice`，该方式与一次性成功确认的生命周期一致，也不会影响置顶、删除依赖的现有侧栏反馈。

### 通过页面组件测试区分反馈通道

扩展现有 Ant Design 消息 mock，断言重命名成功调用 `message.success`，并断言页面不出现侧栏 `role="status"`。这比只检查 mutation 调用更能保证用户可见行为。

## Risks / Trade-offs

- [全局浮层被用户短暂忽略] → 成功后会话项仍立即恢复正常展示并显示最新名称；用户不依赖浮层继续操作。
- [误改置顶或删除提示通道] → 变更只替换 `saveRename` 成功分支，并保留相关测试。

## Migration Plan

前端静态资源随正常部署发布；不涉及数据迁移或后端发布顺序。若需回滚，恢复重命名成功分支对 `listActionNotice` 的写入即可。

## Open Questions

无。
