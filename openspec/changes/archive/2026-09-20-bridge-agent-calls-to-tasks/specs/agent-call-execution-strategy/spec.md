## MODIFIED Requirements

### Requirement: 执行策略契约必须保留未来延迟执行的扩展位置

系统 MUST 使用协议无关的内部执行结果边界，使执行策略可以表达已完成结果、受控失败和带 opaque execution reference 的已接收结果。任何产生异步结果的策略 MUST 只能把已授权、且由服务端异步档案登记的 Agent Call 交给 Agent→Task 桥接，并 MUST 通过受信任 Task 提交能力创建任务；不得自行访问 Task Repository、接受客户端 Task 参数或开放通用任务创建。默认同步策略 MUST NOT 创建 Task 或产生已接收异步结果。

#### Scenario: 当前同步策略不产生任务引用

- **WHEN** 当前能力通过默认同步策略执行
- **THEN** 系统只返回现有同步完成或失败状态
- **AND** 不创建 Task、不写入 Task 存储且不返回任务 ID

#### Scenario: 异步策略通过受控桥接返回引用

- **WHEN** 已授权 Agent Call 命中服务端登记的异步档案，且桥接成功创建或幂等取得 Task
- **THEN** 策略返回 `accepted` 和 opaque execution reference
- **AND** Task owner、task type、尝试策略和展示字段均来自服务端固定档案

#### Scenario: 异步策略不得绕过 Task 提交边界

- **WHEN** 异步策略尝试直接访问 Task Repository、使用客户端提供的 task type 或在未登记档案下创建 Task
- **THEN** 系统拒绝该执行
- **AND** 不创建 Task、Attempt、Event 或提交回执

#### Scenario: 后续策略可在不修改授权流程的情况下扩展

- **WHEN** 测试注入一个符合执行策略契约的同步或异步替身实现
- **THEN** Dispatcher 可以在同一套目录、权限、确认和错误边界下调用该替身
- **AND** 业务 Agent、协议适配器和 Task Domain 不需要为该替身增加直接依赖
