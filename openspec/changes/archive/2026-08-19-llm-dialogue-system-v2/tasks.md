## 1. 子 Change 收口

- [x] 1.1 核对 Conversation 基础和 Dialogue Runtime 的 5 个叶子 Change 已归档；完成条件：模型存储、消息写入与读取、上下文构建和基础对话均有归档任务记录且没有未勾选项。
- [x] 1.2 核对 Interaction 控制和 Agent 授权的 6 个叶子 Change 已归档；完成条件：能力目录、候选识别、提议确认、结构化调用、策略校验和受控分发均有归档任务记录且没有未勾选项。
- [x] 1.3 核对 Dialogue-Agent 集成和 V1 退场的 3 个叶子 Change 已归档；完成条件：调用结果落盘、结果续写和旧入口退场均有归档任务记录且没有未勾选项。

## 2. 整体规格与验收

- [x] 2.1 建立 V2 对话系统组合规格；完成条件：规格覆盖普通对话、确认后的 Agent 调用、续写失败和 V1 入口退场，且不重复叶子 Change 的内部实现细节。
- [x] 2.2 运行后端、前端和规格校验；完成条件：`python -m pytest -q` 为 393 passed，前端单进程 Vitest 为 22 passed，`npm run build` 与 `python -m compileall -q app tests` 通过，OpenSpec 严格校验通过。
- [x] 2.3 记录静态检查残留；完成条件：明确全量 `ruff check app tests` 仍只报告 `tests/agent/tender/test_prompts.py` 和 `tests/application/test_knowledge_management_http.py` 的 3 个既有问题，未将其标记为本 Change 已通过的检查。
