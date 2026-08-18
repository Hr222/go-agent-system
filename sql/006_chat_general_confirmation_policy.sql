-- 将普通 Chat 调整为无需人工批准的受控能力。
-- 该迁移可重复执行：新库由 005 的种子直接获得 never，已有库在此处收敛。
UPDATE platform_capability
SET confirmation_policy = 'never',
    updated_at = NOW()
WHERE code = 'chat.general'
  AND confirmation_policy IS DISTINCT FROM 'never';
