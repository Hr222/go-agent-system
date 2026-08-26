## 1. 建立目标包边界

- [x] 1.1 创建 `platform` 与 `business` 包根目录，并迁移 LLM、Knowledge、Ingestion、Context、Dialogue、Attachment、Security 等平台模块，保持各模块内部 `application/domain/ports` 结构不变。
- [x] 1.2 将 `online` 和 `agent/tender` 迁移到业务应用包，确认 Tender 仍作为业务 Agent 验证样例，不新增平台级职责。
- [x] 1.3 将 `agent/runtime` 迁移到 `platform/agent/runtime`，并保留 `interaction` 与 `conversation` 的内部文件结构不变。

## 2. 更新依赖与组装

- [x] 2.1 按目标包路径更新模块导出、跨模块导入和测试导入，确保平台层不依赖业务层。
- [x] 2.2 更新平台模块的包导出和导入路径，确保 `interaction`、`conversation`、`dialogue` 和 `agent/runtime` 的现有职责与依赖关系不变。
- [x] 2.3 更新 `app/composition/` 和 `ApplicationContainer` 的导入、依赖注入、固定 `dispatch_key` 绑定以及协议适配器引用。
- [x] 2.4 删除旧的 `app/modules` 混合物理路径，确认不存在并行实现或长期兼容别名。

## 3. 验证外部行为与边界

- [x] 3.1 更新并运行架构边界测试，验证 Interfaces、Platform、Business、Infrastructure 和 Composition Root 的依赖方向符合设计。
- [x] 3.2 运行后端模块测试和全量测试，确认 HTTP、MCP、Function Calling、知识检索、对话和 Tender Agent 行为不变。
- [x] 3.3 运行 `python -m compileall -q app tests`、`ruff check app tests`、前端构建和 `git diff --check`，记录迁移后的验证结果。
