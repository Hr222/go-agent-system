-- 为 Conversation 增加可编辑的话题概括；历史记录保持 NULL，不猜测既有主题。
ALTER TABLE conversation
    ADD COLUMN IF NOT EXISTS topic_summary TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_conversation_topic_summary_valid'
          AND conrelid = 'conversation'::regclass
    ) THEN
        ALTER TABLE conversation
            ADD CONSTRAINT chk_conversation_topic_summary_valid
            CHECK (
                topic_summary IS NULL
                OR (
                    btrim(topic_summary) <> ''
                    AND topic_summary = btrim(topic_summary)
                    AND position(E'\\n' in topic_summary) = 0
                    AND position(E'\\r' in topic_summary) = 0
                    AND char_length(topic_summary) <= 80
                )
            );
    END IF;
END $$;
