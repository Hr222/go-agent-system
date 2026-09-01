## 1. 受控通用 Chat 兜底

- [x] 1.1 在 Interaction Gateway 中仅为 `unrecognized` 结果构造固定 `chat.general` 兜底评估，并复用目录、策略、分发和输入复核；完成条件：自然追问携带原始文本获得受控 `authorized` 分流。
- [x] 1.2 保留 `needs_clarification`、目录或索引不可用、通用 Chat 不可用及非 `never` 策略的原有受控结果；完成条件：这些分支不创建通用 Chat 直接执行对象。

## 2. 回归验证

- [x] 2.1 增加 Gateway 单元测试，覆盖未识别追问兜底、原始输入保留、待澄清请求不回退和通用 Chat 不可用；完成条件：测试证明兜底不绕过业务确认边界。
- [x] 2.2 增加 Interaction 流式测试，覆盖兜底授权后返回 `meta`、`delta`、`complete` 并将同一 Conversation 交给流式运行时；完成条件：SSE 事件和 Conversation 标识保持既有契约。
- [x] 2.3 运行相关后端测试、OpenSpec 严格校验及前端测试和构建；完成条件：所有命令通过，或记录可复现的外部阻塞原因。
- [x] 2.4 使用浏览器发送自然语言两轮追问并刷新页面；完成条件：第二轮无需提示“通用 LLM”即可读到首轮上下文，并能从历史恢复。
