## 1. 集成前置条件

- [x] 1.1 确认 `add-generic-embedding-port`、`add-platform-capability-catalog`、`add-intent-candidate-retrieval` 和 `add-structured-intent-recognition-confirmation` 均已完成、验证并归档；完成条件：四项能力的主规格已同步且依赖版本可用。
- [x] 1.2 确认 `add-request-principal-resolver` 已完成、验证并归档；完成条件：主规格 `request-principal-resolution` 可用，匿名主体默认空权限。
- [x] 1.3 审核能力目录中的 Agent 与非 Agent 分发键，并校准目录 Input Schema；完成条件：每个拟暴露能力都有唯一、可组装的受控目标，`policy.review` 输入可映射到真实 Application Command。

## 2. 统一入口与受控分发

- [x] 2.1 新增 Interaction HTTP Schema、Assembler、Route 和 Composition Root 组装，并消费已归档的 `PrincipalResolver`；完成条件：自然语言识别与确认请求均经 Application 层，只读取可信 `RequestPrincipal`，不泄漏 HTTP 或 LLM Provider 对象，客户端不能自报权限。
- [x] 2.2 实现仅接受有效确认结果的 Controlled Dispatcher 和短期一次性提议存储；完成条件：目标由固定分发键映射到 Agent Runtime 或 Online Use Case，未确认、已取消、已消费或匿名无权限请求不持有或调用执行器。
- [x] 2.3 保持既有直接 Chat、Agent、RAG 和知识库接口不变；完成条件：既有接口的回归测试无需经过统一入口仍然通过。

## 3. 前端确认交互

- [x] 3.1 将意图识别嵌入现有 Chat 发送流程，并在对话消息流中展示待确认能力、确认和取消状态；完成条件：用户不需要进入独立意图识别页面，前端只渲染受控响应，不拼接 Prompt 或决定分发目标。
- [x] 3.2 在 Chat 消息流中处理识别失败、澄清、取消、确认后成功和分发失败状态；完成条件：每个状态有明确可操作或可理解的对话结果，且不会重复提交执行。

## 4. 端到端验收与归档

- [x] 4.1 增加后端集成测试，覆盖 Agent、非 Agent、资料缺失、取消、未确认、匿名权限、伪造权限、重复确认和分发失败；完成条件：测试通过替换 HTTP 主体解析依赖证明只有有效确认且服务端主体有权限时才产生目标用例调用。
- [x] 4.2 运行前端类型检查、构建和交互测试；完成条件：统一入口在现有前端架构中通过构建且不破坏既有页面。
- [x] 4.3 完成安全、兼容性和人工验收后归档本 Change；完成条件：OpenSpec 严格校验通过、任务全部勾选，并记录前五个子 Change 的归档引用。

### 4.3 验收记录（2026-08-18）

- 后端全量回归：`272 passed`。
- 前端交互测试：`28 passed`；TypeScript 类型检查和生产构建通过。
- Ruff：交互、安全和相关测试代码检查通过。
- 浏览器人工验收：普通 Chat 直接流式完成；知识库请求先显示批准卡，取消后显示未执行，再次明确批准后才完成知识库回答。
- 子 Change 归档引用：
  - `openspec/changes/archive/2026-08-17-add-generic-embedding-port`
  - `openspec/changes/archive/2026-08-17-add-platform-capability-catalog`
  - `openspec/changes/archive/2026-08-17-add-intent-candidate-retrieval`
  - `openspec/changes/archive/2026-08-17-add-structured-intent-recognition-confirmation`
  - `openspec/changes/archive/2026-08-17-add-request-principal-resolver`
