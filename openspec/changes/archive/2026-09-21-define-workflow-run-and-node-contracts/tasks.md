## 1. Workflow Domain 契约

- [x] 1.1 新增 Workflow Definition/Version、Node、Edge 和安全输入/输出引用模型；完成条件：能拒绝重复节点、非法边、环、未知节点类型和不受支持的能力绑定，并保持已注册 Version 不可变。
- [x] 1.2 新增 Workflow Run、Node Run、状态枚举和幂等命令；完成条件：Run/Node 的合法状态流转覆盖 queued、running、accepted、succeeded、failed、cancel_requested、cancelled、skipped，且重复终态命令不产生第二条事件。

## 2. Application 与 Ports

- [x] 2.1 新增固定 Definition Registry、能力目录校验 Port 和受信任 Run Application；完成条件：创建 Run 时重新校验主体权限、Version、输入契约和幂等键，不接受客户端执行器、URL 或任意 dispatch key。
- [x] 2.2 新增 Node Executor Port、受控执行结果和依赖就绪计算；完成条件：前置节点未成功时不创建执行尝试，节点可表达 completed、accepted 和安全 failed，accepted 只携带 opaque execution reference。
- [x] 2.3 实现 Run/Node 的取消、失败、重试和主体隔离应用命令；完成条件：取消先进入 cancel_requested，错误按可重试/不可重试分类，跨主体读取或控制返回稳定隔离结果。

## 3. 持久化与 Composition

- [x] 3.1 为 Workflow Run、Node Run 和安全事件增加 PostgreSQL 模型、映射、Repository Port 实现及 SQL 迁移；完成条件：唯一幂等约束、主体索引、节点/边关联和事件顺序约束在事务中生效，不保存原始输入、lease 或 Provider 响应。
- [x] 3.2 在 Composition Root 注册固定 Workflow Version 与 Tender 能力节点验证绑定；完成条件：只组装已登记能力，未注册 Version 或能力绑定错误时服务启动/加载失败，不新增公开 HTTP、MCP 或 Function Calling 路由。

## 4. 验证与文档

- [x] 4.1 增加 Workflow Domain/Application/Repository 的状态机、幂等、依赖、取消、权限和敏感字段测试；完成条件：内存替身覆盖成功、accepted、失败、重试、取消和冲突分支。
- [x] 4.2 增加架构边界、PostgreSQL 映射和 Composition 测试，并确认现有 Task、Dialogue、Tender MCP 回归不变；完成条件：不出现 Workflow 对 HTTP/ORM/Provider 的错误依赖，外部 MCP 仍同步返回 EmbeddedResource。
- [x] 4.3 更新 `ARCHITECTURE.md`、系统看板和 README，说明 Workflow 目前仅有后端契约、固定 Version 和受信任入口；完成条件：明确编辑器、动态编排、多 Agent/SubAgent、下载和终态会话回传仍未实现，并通过全量测试、lint、编译、OpenSpec 严格校验和差异检查。
