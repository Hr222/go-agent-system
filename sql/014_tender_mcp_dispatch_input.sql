-- 将 Tender MCP 统一分发所需的服务端附件输入契约同步到既有能力目录。
UPDATE platform_capability
SET input_schema = '{"type":"object","properties":{"source_document":{"type":"string","x-attachment":{"allowed_media_types":["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],"max_size_bytes":52428800,"max_count":1}},"start_block_id":{"type":"string"},"end_block_id":{"type":"string"},"output_name":{"type":["string","null"]}}}'::jsonb,
    required_fields = '["source_document","start_block_id","end_block_id"]'::jsonb,
    updated_at = NOW()
WHERE code = 'tender.extract_bid_format_section'
  AND (
      input_schema IS DISTINCT FROM '{"type":"object","properties":{"source_document":{"type":"string","x-attachment":{"allowed_media_types":["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],"max_size_bytes":52428800,"max_count":1}},"start_block_id":{"type":"string"},"end_block_id":{"type":"string"},"output_name":{"type":["string","null"]}}}'::jsonb
      OR required_fields IS DISTINCT FROM '["source_document","start_block_id","end_block_id"]'::jsonb
  );

UPDATE platform_capability
SET input_schema = '{"type":"object","properties":{"source_document":{"type":"string","x-attachment":{"allowed_media_types":["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],"max_size_bytes":52428800,"max_count":1}},"start_block_id":{"type":"string"},"end_block_id":{"type":"string"},"context_radius":{"type":"integer"}}}'::jsonb,
    required_fields = '["source_document","start_block_id","end_block_id"]'::jsonb,
    updated_at = NOW()
WHERE code = 'tender.verify_extraction_boundary'
  AND (
      input_schema IS DISTINCT FROM '{"type":"object","properties":{"source_document":{"type":"string","x-attachment":{"allowed_media_types":["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],"max_size_bytes":52428800,"max_count":1}},"start_block_id":{"type":"string"},"end_block_id":{"type":"string"},"context_radius":{"type":"integer"}}}'::jsonb
      OR required_fields IS DISTINCT FROM '["source_document","start_block_id","end_block_id"]'::jsonb
  );
