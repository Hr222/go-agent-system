-- 为既有 Conversation 添加资源归属。这个 migration 不会猜测历史记录的所有者。
--
-- 若 conversation 表中已有记录，先在同一数据库会话设置受控回填主体，再执行本脚本：
--   BEGIN;
--   SELECT set_config(
--       'app.conversation_owner_backfill_subject',
--       '受控迁移主体',
--       true
--   );
--   \i sql/010_conversation_owner_subject.sql
--   COMMIT;
--
-- 未设置回填主体时，发现历史记录会报错，且不会施加 NOT NULL 约束。

ALTER TABLE conversation
    ADD COLUMN IF NOT EXISTS owner_subject TEXT;

DO $$
DECLARE
    backfill_subject TEXT := NULLIF(
        btrim(current_setting('app.conversation_owner_backfill_subject', true)),
        ''
    );
BEGIN
    IF EXISTS (
        SELECT 1
        FROM conversation
        WHERE owner_subject IS NULL OR btrim(owner_subject) = ''
    ) THEN
        IF backfill_subject IS NULL THEN
            RAISE EXCEPTION
                'conversation.owner_subject 回填需要受控迁移主体；请先设置 app.conversation_owner_backfill_subject。';
        END IF;

        UPDATE conversation
        SET owner_subject = backfill_subject
        WHERE owner_subject IS NULL OR btrim(owner_subject) = '';
    END IF;
END $$;

ALTER TABLE conversation
    ALTER COLUMN owner_subject SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_conversation_owner_subject_not_blank'
          AND conrelid = 'conversation'::regclass
    ) THEN
        ALTER TABLE conversation
            ADD CONSTRAINT chk_conversation_owner_subject_not_blank
            CHECK (btrim(owner_subject) <> '');
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_conversation_owner_subject
    ON conversation(owner_subject);
