## Why

现有 `PolicyUploadService` 已具备真实临时文件写入、大小限制、路径隔离和清理能力，但实现名称和配置属于政策入库。需要在不破坏旧流程的前提下提供可复用的附件存储实现。

## What Changes

- 将通用暂存、读取、清理能力适配到附件契约。
- 使用随机 ID、分片写入、原子落盘和目录越界校验。
- 为动态文件生命周期增加真实临时文件系统测试。

## Capabilities

### New Capabilities

- `attachment-storage`: 可复用的真实附件暂存与读取能力。

### Modified Capabilities

- 无。

## Impact

影响文件系统基础设施、通用配置和测试；现有政策上传流程必须保持兼容，不引入数据库依赖。

