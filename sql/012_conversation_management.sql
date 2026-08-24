-- Conversation 管理状态：历史会话默认未置顶。
ALTER TABLE conversation
    ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE conversation
SET is_pinned = FALSE
WHERE is_pinned IS NULL;

ALTER TABLE conversation
    ALTER COLUMN is_pinned SET DEFAULT FALSE,
    ALTER COLUMN is_pinned SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_conversation_owner_pinned_updated
    ON conversation(owner_subject, is_pinned DESC, updated_at DESC, id DESC);
