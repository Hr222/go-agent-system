## Why

Task 工作区已经接入真实详情，但当前实现将“终态不轮询”错误地实现为“不查询事件”，使已完成、失败或取消的任务没有事件时间线。该错误会直接违背任务详情的可追溯性，需要在结果资源 Change 前独立修复。

## What Changes

- 将任务事件查询与事件轮询解耦：所有可访问任务首次读取事件，只有活动任务周期性刷新。
- 增加终态和活动状态的 hook 回归测试。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `task-management-workspace`: 任务详情在终态也读取并展示已有事件，终态只停止轮询。

## Impact

- 仅影响前端 Task Query hook、详情页调用和测试。
- 不改变 HTTP 契约、数据库、任务状态或主体隔离。
