## MODIFIED Requirements

### Requirement: 任务详情必须显示状态和事件

任务详情页 MUST 查询真实任务详情和 owner-scoped 事件，并展示加载、失败和事件为空状态。任务进入终态后 MUST 保留已读取的事件时间线，并停止事件轮询。

#### Scenario: 任务详情成功
- **WHEN** 任务详情和事件查询成功
- **THEN** 页面显示任务状态、创建/更新时间、结果摘要或失败信息，以及按顺序排列的事件

#### Scenario: 活动任务
- **WHEN** 任务状态为 queued、running、retry_wait 或 cancel_requested
- **THEN** 页面周期性刷新任务和事件，直到进入终态或页面离开

#### Scenario: 终态任务
- **WHEN** 任务状态为 succeeded、failed 或 cancelled
- **THEN** 页面首次读取并展示已有事件，且不再周期性刷新事件

#### Scenario: 任务不可用
- **WHEN** 后端返回任务不可用
- **THEN** 页面显示任务不存在或不可访问状态，不展示旧的 mock 详情
