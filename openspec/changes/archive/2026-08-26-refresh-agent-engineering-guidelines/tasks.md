## 1. 更新 LLM 项目认知与文档职责

- [x] 1.1 重写 `agent.md` 的事实来源优先级，移除固定 Phase、进度表和未来路线内容。
- [x] 1.2 在 `agent.md` 中加入当前平台/业务/横向技术最小认知模型，并准确说明 Gateway、Agent Management、Ingestion、Knowledge/RAG、Online 与 Tender 边界。
- [x] 1.3 更新 `openspec/config.yaml` 的项目上下文，将旧的 `application/modules` 路径和不准确模块边界改为当前目录与术语。

## 2. 更新开发守则与中文注释规则

- [x] 2.1 将讨论、评审、诊断和实施请求的处理协议写入 `agent.md`，明确未获实施指令时不得修改文件。
- [x] 2.2 将中文注释规则写入 `agent.md`，覆盖复杂逻辑、关键流程、非直观规则、安全边界、兼容逻辑和重要取舍，并明确简单代码不逐行注释。
- [x] 2.3 对齐 Domain、Interfaces、Application Capability、Ports、Infrastructure 和 Composition Root 的开发约束，避免重复完整架构说明。

## 3. 更新验证与 Git 交付规则

- [x] 3.1 更新测试、静态检查、前端构建、OpenSpec 校验和 `git diff --check` 的验收要求。
- [x] 3.2 补充提交前显式暂存和 staged diff 检查规则，覆盖 `.tmp`、`.runtime`、`backups`、真实 SQL 备份、OCR 输出、`.env` 和真实业务资料。
- [x] 3.3 固化中文提交标题格式、单一变更提交原则、Change 归档顺序和远程推送授权规则。

## 4. 一致性验证

- [x] 4.1 检查 `agent.md` 和 `openspec/config.yaml` 不再包含 `application/modules`、错误的 `OpenSpace`、固定阶段状态或与 `ARCHITECTURE.md` 冲突的边界。
- [x] 4.2 检查规则中的平台/业务目录、Agent Management、Gateway、Ingestion、Knowledge/RAG 与中文注释要求能够对应本 Change 的规格场景。
- [x] 4.3 运行 `openspec validate "refresh-agent-engineering-guidelines" --strict`、Markdown 链接检查和 `git diff --check`，完成人工审阅后再标记 Change 完成。
