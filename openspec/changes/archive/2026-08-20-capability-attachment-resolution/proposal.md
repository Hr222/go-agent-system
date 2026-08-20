## Why

附件上传和访问控制完成后，Interaction Gateway 仍需要把不透明附件引用安全地转换成能力可消费的内部输入。该转换必须通用，不能把 Tender 或某个文件格式写进附件存储层。

## What Changes

- 定义能力级附件字段声明和解析 Port。
- 按能力允许的媒体类型、大小和数量校验附件。
- 在服务端读取附件内容并生成内部输入，禁止客户端直接覆盖解析结果。

## Capabilities

### New Capabilities

- `capability-attachment-resolution`: 将附件引用解析为受控能力输入。

### Modified Capabilities

- 无。

## Impact

影响 Interaction 输入校验、附件 Port 和能力目录元数据；不实现具体 Agent 适配器，不改变前端上传组件。

