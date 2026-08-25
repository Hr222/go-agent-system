## 1. GLM Profile 配置

- [x] 1.1 在 `Settings` 和 `LlmProviderConfig` 中定义 `resource`、`coding_plan` Profile 选择及各自独立的端点、模型、超时、温度和输出预算；完成条件：默认 GLM 配置解析为资源包 Profile，显式 Coding Plan 配置只返回 Coding Plan 参数。（对应：GLM 运行 Profile 独立选择、资源包与 Coding Plan 配置隔离）
- [x] 1.2 保留旧 `ZHIPU_*` 变量作为资源包 Profile 的回退来源，并让新 `ZHIPU_RESOURCE_*` 变量优先；完成条件：旧部署配置不失效，新旧同时存在时选择新资源包变量。（对应：旧 GLM 配置迁移兼容）

## 2. 基础设施组装与受控验证

- [x] 2.1 让 OpenAI-compatible Client Factory 以所选 Profile 创建 Client 并输出脱敏 Profile、端点和模型日志；完成条件：GLM 的 Chat、Structured 与 RAG 继续共享同一所选 Profile Client，DeepSeek 不读取 GLM Profile。（对应：GLM 运行 Profile 独立选择、Profile 可验证且不泄露敏感数据）
- [x] 2.2 增加仅由服务端环境变量选择 Profile 的最小 GLM 冒烟入口；完成条件：可分别验证资源包和 Coding Plan 的文本调用，输出不含密钥、完整提示词或完整模型响应。（对应：受控验证两个 Profile、配置或上游失败）

## 3. 配置迁移与自动化验证

- [x] 3.1 更新 `.env.example` 和本地 `.env` 为资源包默认、Coding Plan 保留的双 Profile 配置；完成条件：示例不含真实密钥，本地默认选 `resource` 且 Coding Plan 参数仍独立保留。
- [x] 3.2 补充 Settings、Client Factory、Composition Root 与冒烟入口测试；完成条件：覆盖默认 Profile、显式切换、隔离、新变量优先、旧变量回退、缺失密钥和脱敏输出。
- [x] 3.3 运行定向后端测试、架构边界测试、`ruff check`、`compileall`、OpenSpec 严格校验和 `git diff --check`；完成条件：全部通过且无无关文件变更。

## 4. 真实 Profile 验证

- [x] 4.1 使用资源包 Profile 执行最小文本 GLM 冒烟，并在本地 Chat 页面完成一次普通流式对话和一次结构化意图识别；完成条件：日志确认使用资源包端点和模型，两个调用均返回受控结果。
- [x] 4.2 使用 Coding Plan Profile 执行相同最小文本冒烟后切回资源包 Profile；完成条件：Coding Plan 连通性通过，最终运行配置恢复 `resource`，不将 Coding Plan 切为当前主流量。
