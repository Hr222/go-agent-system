## 1. 建立统一架构基线

- [x] 1.1 将 `ARCHITECTURE_V1.md` 的平台分层、模块职责、依赖约束、知识库与 HTTP 边界合并到 `ARCHITECTURE.md`，并保持与现有代码事实一致。
- [x] 1.2 将 `ARCHITECTURE_V2.md` 的多轮对话、LLM、Interaction Gateway、Agent Runtime、主体归属和演化边界合并到 `ARCHITECTURE.md`，清晰标出已实现、预留和非目标。
- [x] 1.3 将 `FRONTEND_ARCHITECTURE.md` 的工程分层、请求与状态规范、页面和 Agent/知识库前端边界合并到 `ARCHITECTURE.md`，并明确前后端接口边界。

## 2. 清理已合并的旧文档

- [x] 2.1 从 `ARCHITECTURE.md` 删除历史快照说明，增加按后端到前端排列的文档目录，并删除三份已合并的旧架构文档。
- [x] 2.2 更新 `agent.md`、OpenSpec 配置、OpenSpec 使用约定、当前阶段看板和未归档 Change，使其只引用 `ARCHITECTURE.md`。

## 3. 验证

- [x] 3.1 复核统一文档包含后端到前端目录、分层职责、依赖方向、对话请求流程、前端边界和当前能力状态，且不把未实现能力描述为已完成。
- [x] 3.2 运行严格 OpenSpec 校验和当前维护文档引用检查，确认旧架构文件已删除且没有遗留引用。
