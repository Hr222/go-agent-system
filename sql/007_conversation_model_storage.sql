-- 会话与消息的最小持久化模型；不包含 HTTP、LLM 或 Agent 行为。
CREATE TABLE IF NOT EXISTS conversation (
    id UUID PRIMARY KEY,
    owner_subject TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_conversation_owner_subject_not_blank CHECK (
        btrim(owner_subject) <> ''
    )
);

CREATE INDEX IF NOT EXISTS idx_conversation_owner_subject
    ON conversation(owner_subject);

CREATE TABLE IF NOT EXISTS conversation_message (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sequence BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_conversation_message_role CHECK (
        role IN ('system', 'user', 'assistant')
    ),
    CONSTRAINT chk_conversation_message_content_not_blank CHECK (
        btrim(content) <> ''
    ),
    CONSTRAINT chk_conversation_message_sequence_positive CHECK (
        sequence > 0
    ),
    CONSTRAINT uq_conversation_message_conversation_sequence UNIQUE (
        conversation_id,
        sequence
    )
);

-- 唯一约束会创建相同列序的 B-tree 索引，供按会话、消息顺序读取历史使用。
