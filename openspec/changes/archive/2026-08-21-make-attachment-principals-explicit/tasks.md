## 1. 附件归属前置条件

- [x] 1.1 将 `AttachmentAccessContext` 和文件暂存改为拒绝缺少非空主体的创建上下文，且不生成目录或记录。
- [x] 1.2 在 HTTP 上传边界对匿名主体返回 `403 ATTACHMENT_PRINCIPAL_REQUIRED`，并保持其他上传输入错误的既有 `400` 契约。

## 2. 开发配置与回归覆盖

- [x] 2.1 更新 `.env.example`，提供仅用于受控本地开发的静态主体和执行权限示例。
- [x] 2.2 覆盖直接暂存、匿名 HTTP 上传和具名主体 HTTP 上传，验证没有无归属附件泄漏。

## 3. 验证

- [x] 3.1 运行受影响的附件和安全测试，并运行全量 pytest。
- [x] 3.2 运行 `ruff check`、OpenSpec 严格校验和 `git diff --check`，记录验证结果。

## 验证记录

- `python -m pytest -q tests/attachment/test_filesystem_storage.py tests/attachment/test_upload_http.py tests/security/test_principal_mode_configuration.py tests/security/test_principal_resolver.py`：41 passed。
- `python -m pytest -q`：459 passed。
- `python -m compileall -q app tests`、本批 Python 文件的 `ruff check`、`openspec validate "make-attachment-principals-explicit" --strict` 和 `git diff --check`：通过。
- 仓库级 `ruff check app tests` 仍有 5 个本批未触及的历史问题，位于 `tests/agent/tender/test_prompts.py`、`tests/application/test_knowledge_management_http.py` 和 `tests/interaction/test_security_tender_candidate_visibility.py`。
