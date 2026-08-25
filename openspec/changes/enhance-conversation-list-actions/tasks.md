## 1. Conversation 领域与持久化

- [x] 1.1 为 `Conversation`、`ConversationSummary` 和 mapper 增加 `is_pinned`，默认值为 `false`，并补充领域与存储测试。
- [x] 1.2 添加幂等迁移 `012_conversation_management.sql`，新增非空置顶字段、默认值和主体列表排序所需索引；验证历史会话全部未置顶。
- [x] 1.3 扩展列表游标编码与解码，携带置顶状态并兼容旧两字段游标；补充置顶分组分页不重复、不遗漏测试。

## 2. 后端应用与 HTTP

- [x] 2.1 扩展 Conversation 写端口和 PostgreSQL repository，实现主体范围置顶切换与级联删除，覆盖不存在和数据库失败回滚。
- [x] 2.2 增加 Conversation 管理应用服务和 Composition Root/HTTP dependency 组装，统一复用主体访问校验。
- [x] 2.3 增加 `PATCH /api/v1/conversations/{conversation_id}/pin` 和 `DELETE /api/v1/conversations/{conversation_id}`，映射匿名、越权、无效 UUID 和成功响应。
- [x] 2.4 更新会话列表摘要响应的 `is_pinned` 字段，运行主体隔离、排序、置顶、删除和级联事实 HTTP 测试。

## 3. Chat 前端菜单与状态

- [ ] 3.1 扩展会话列表 API、类型和 React Query hooks，支持置顶、删除和列表缓存失效；补充 API/hook 测试。
- [ ] 3.2 接入会话项重命名菜单与编辑保存/清除，完成失败反馈和菜单关闭。
- [ ] 3.3 接入单项删除菜单、二次确认、成功清理和失败提示。
- [ ] 3.4 接入置顶/取消置顶菜单，刷新列表排序并显示操作反馈；分享仅保留无动作占位项。
- [x] 3.5 调整侧栏滚动与菜单定位，确保编辑区、菜单和删除确认不被裁切；补充组件交互测试。

## 4. 验证与人工验收

- [ ] 4.1 运行后端 Conversation/架构测试、前端 `npm run test -- --run` 和 `npm run build`。
- [ ] 4.2 运行 `openspec validate enhance-conversation-list-actions --strict --no-interactive` 与全库严格校验，并执行 `git diff --check`。
- [ ] 4.3 在本地 Chat 页面按“重命名、删除、置顶”顺序人工验收，并确认分享占位项点击无任何效果及越权失败提示。
