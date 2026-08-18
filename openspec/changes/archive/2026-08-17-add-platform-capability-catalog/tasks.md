## 1. 平台能力目录

- [x] 1.1 定义 `platform_capability` 数据模型、迁移、Repository、Application Port 和校验规则；完成条件：表记录拥有规格要求的全部受控字段，能力代码具有唯一约束。
- [x] 1.2 通过受控迁移或种子数据登记现有 Agent 和至少一个非 Agent 用例；完成条件：两类记录可通过同一查询契约被发现，且不需要管理后台。
- [x] 1.3 在 Composition Root 建立 `dispatch_key` 到固定 Application Use Case 的映射校验；完成条件：未知、类型不匹配或可执行地址形式的分发值在加载时被拒绝。

## 2. Runtime 边界与验证

- [x] 2.1 调整 Agent Runtime 通过 Application Port 和 Repository 消费目录中的 Agent 条目，并移除或隔离平行注册来源；完成条件：Runtime 不再拥有第二份可写能力注册表。
- [x] 2.2 增加迁移、Repository、目录加载、启用状态、权限过滤和 Runtime 消费测试；完成条件：重复、无效、禁用、无权限和非 Agent 记录不会被 Runtime 执行。
