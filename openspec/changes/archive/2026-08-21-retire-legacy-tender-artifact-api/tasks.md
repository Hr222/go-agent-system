## 1. 浏览器旧接口退场

- [x] 1.1 从 HTTP router 移除旧 Tender 同步生成路由，使该地址不再调用 Tender Application 或返回 Base64 文件内容。
- [x] 1.2 将旧 Tender HTTP 回归测试替换为退场测试，验证请求返回 404 且不会触发 Tender Application。

## 2. 前端迁移

- [x] 2.1 移除 Tender 页面及其调用链对旧同步 API、multipart 提交和 Base64 下载的依赖，并保留进入 `/chat` 的用户操作。
- [x] 2.2 补充前端测试，验证 Tender 页面不再包含文件上传或旧 API 请求，并能进入对话入口。

## 3. 验证

- [x] 3.1 运行受影响的后端和前端测试，验证旧接口退场不影响受控对话 Agent 下载链路。
- [x] 3.2 运行 `ruff check`、前端生产构建与 OpenSpec 严格校验，并记录未通过项。
