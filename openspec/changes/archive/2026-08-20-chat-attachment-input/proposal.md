## Why

聊天页的“添加附件”按钮目前没有绑定选择或上传行为。通用附件组件已经可用，但用户无法在自然语言对话中提供招标文件，导致聊天入口无法完成受控的 Tender 调用链路。

## What Changes

- 在聊天页接入现有通用附件选择与上传组件。
- 上传成功后，将服务端返回的安全附件引用按 `source_document` 传递到现有对话请求的 `provided_inputs`。
- 在发送、上传和待确认期间正确限制交互，防止未完成上传的文件进入请求。
- 保持未附带附件的纯文本聊天、服务端意图识别、权限过滤和显式确认行为不变。
- 不新增浏览器端对能力代码、分发目标、文件路径或文件内容的访问。

## Capabilities

### New Capabilities

- `chat-attachment-input`: 聊天页选择、上传并安全传递附件引用的用户交互。

### Modified Capabilities

- 无。

## Impact

- 受影响前端：`frontend/src/features/chat/pages/ChatPage.tsx` 及其测试，复用 `features/attachment` 的组件与类型。
- 复用现有 `POST /api/v1/attachments/upload` 和 `/api/v1/interaction/chat/stream`；不修改 HTTP 契约、数据库结构、主体解析或权限配置。
- 受控附件仍由服务端按能力声明解析，前端只保留安全的动态附件引用。
