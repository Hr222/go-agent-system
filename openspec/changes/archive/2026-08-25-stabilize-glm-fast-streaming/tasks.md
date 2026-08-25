## 1. GLM Profile thinking 策略

- [x] 1.1 在 `Settings` 与 `LlmProviderConfig` 中为资源包、Coding Plan 定义独立的 thinking 配置与默认值；完成条件：资源包默认 `disabled`、Coding Plan 默认 `low`，覆盖一个 Profile 不影响另一个 Profile。（对应：资源包与 Coding Plan 配置隔离）
- [x] 1.2 更新 `.env.example` 的双 Profile 配置说明；完成条件：示例只含非敏感默认值，明确 thinking 仅由服务端环境变量选择。

## 2. Provider 与流式活动适配

- [x] 2.1 让 GLM 的普通 Chat、流式 Chat、结构化调用和 RAG 调用均从已选 Profile 显式发送 thinking；完成条件：请求只使用 Provider 配置组的策略，DeepSeek 现有行为不变。（对应：GLM 调用显式使用 Profile thinking 策略）
- [x] 2.2 在流式 LLM Port 中增加不含 reasoning 文本的上游活动标记，并由 OpenAI-compatible Chat Adapter 识别正文或 reasoning；完成条件：内部 reasoning 不作为 `content`、日志或持久化数据输出。（对应：流式首段等待识别上游活动）
- [x] 2.3 将 Interaction Chat 首段等待改为首个上游活动，保持既有 SSE 事件和受控超时/关闭语义；完成条件：reasoning 先到时先发 `meta`，正文仍只发 `delta`。（对应：普通 Chat SSE 返回 Conversation 标识）

## 3. 自动化验证

- [x] 3.1 补充 Profile 配置与 Provider 请求测试；完成条件：覆盖两个默认值、独立覆盖、Chat/Structured/RAG 的显式 thinking 和 DeepSeek 隔离。
- [x] 3.2 补充流式 Adapter 与 Interaction 测试；完成条件：覆盖 reasoning 活动先到、无活动超时、reasoning 不泄漏和既有正文/持久化行为。

## 4. 受控验收

- [x] 4.1 运行定向测试、全库测试、架构测试、Ruff、编译、OpenSpec 严格校验和 `git diff --check`；完成条件：全部通过且无无关文件变更。
- [x] 4.2 分别以资源包和 Coding Plan 执行最小 GLM 文本冒烟，并将最终 Profile 恢复为 `resource`；完成条件：两个请求均显式使用目标 thinking 策略，输出不含密钥、提示词或 reasoning 正文。
