## 1. Conversation 归属模型

- [x] 1.1 在 Conversation Domain、mapper、ORM 和 SQL 迁移中加入经校验的 `owner_subject`，并建立按主体查询所需索引。
- [x] 1.2 实现既有数据的受控回填/停止策略，验证迁移不会静默错误归属历史数据。

## 2. 验证

- [x] 2.1 覆盖有效静态主体、无效归属键和持久化往返的单元/基础设施测试。
- [x] 2.2 运行相关 pytest、数据库迁移验证和 OpenSpec 严格校验。

## 验证记录

- Conversation、Dialogue 和基础设施定向测试：95 passed；包含隔离 PostgreSQL schema 中的 migration 阻断与显式回填测试。
- `python -m pytest -q`：466 passed。
- `python -m compileall -q app tests`、本批 Python 文件的 `ruff check`、`openspec validate "add-conversation-owner-subject" --strict` 和 `git diff --check`：通过。
- 仓库级 `ruff check app tests` 仍有 5 个本批未触及的历史问题，位于 `tests/agent/tender/test_prompts.py`、`tests/application/test_knowledge_management_http.py` 和 `tests/interaction/test_security_tender_candidate_visibility.py`。
