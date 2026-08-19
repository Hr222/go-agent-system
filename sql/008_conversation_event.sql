-- Conversation Agent 调用生命周期事件。事件与自然语言消息分表，避免污染模型上下文。
CREATE TABLE IF NOT EXISTS conversation_event (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    call_id TEXT NOT NULL,
    capability_code TEXT NOT NULL,
    sequence BIGINT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_conversation_event_type CHECK (
        event_type IN ('agent_call', 'agent_result', 'agent_error')
    ),
    CONSTRAINT chk_conversation_event_call_id_not_blank CHECK (btrim(call_id) <> ''),
    CONSTRAINT chk_conversation_event_capability_not_blank CHECK (btrim(capability_code) <> ''),
    CONSTRAINT chk_conversation_event_sequence_positive CHECK (sequence > 0),
    CONSTRAINT chk_conversation_event_payload_object CHECK (jsonb_typeof(payload) = 'object'),
    CONSTRAINT uq_conversation_event_conversation_sequence UNIQUE (conversation_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_conversation_event_call_id
    ON conversation_event(conversation_id, call_id, sequence);
