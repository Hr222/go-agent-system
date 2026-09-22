## Context

`useTaskEvents` 的启用参数同时控制首次请求和轮询。详情页将它设为“Task 存在且活动”，因此终态任务从未发起事件请求。

## Goals / Non-Goals

**Goals:**

- 每个有效 Task 详情首次读取事件。
- 只有活动状态按固定间隔刷新事件。

**Non-Goals:**

- 不改变事件分页、事件排序或后端查询参数。
- 不为终态任务增加后台轮询。

## Decisions

将 `enabled` 固定为有效 `taskId`，并把活动状态作为独立 `poll` 参数控制 `refetchInterval`。这既保留终态的首次读，也避免终态持续请求。

## Risks / Trade-offs

- [详情页增加一次终态事件请求] -> 这是展示可追溯事件的必要请求，且不再重复轮询。
