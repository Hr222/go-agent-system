-- 将 Tender 骨架生成能力切换到受控附件引用输入。
-- 新库由 005 的种子直接获得该契约；已有库执行本迁移以收敛目录定义。
UPDATE platform_capability
SET input_schema = '{"type":"object","properties":{"source_document":{"type":"string","x-attachment":{"allowed_media_types":["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],"max_size_bytes":52428800,"max_count":1}},"user_focus":{"type":["string","null"]}},"additionalProperties":false}'::jsonb,
    required_fields = '["source_document"]'::jsonb,
    updated_at = NOW()
WHERE code = 'tender.generate_bid_skeleton'
  AND (
      input_schema IS DISTINCT FROM '{"type":"object","properties":{"source_document":{"type":"string","x-attachment":{"allowed_media_types":["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],"max_size_bytes":52428800,"max_count":1}},"user_focus":{"type":["string","null"]}},"additionalProperties":false}'::jsonb
      OR required_fields IS DISTINCT FROM '["source_document"]'::jsonb
  );
