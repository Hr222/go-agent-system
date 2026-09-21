-- Workflow Run/Node 生命周期事实。仅保存安全摘要与不透明执行引用。

CREATE TABLE IF NOT EXISTS workflow_run (
    id UUID PRIMARY KEY,
    workflow_code TEXT NOT NULL,
    workflow_version TEXT NOT NULL,
    owner_subject TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    result_summary TEXT,
    failure_code TEXT,
    cancel_requested_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_workflow_run_submission UNIQUE (owner_subject, workflow_code, workflow_version, idempotency_key),
    CONSTRAINT chk_workflow_run_owner_not_blank CHECK (btrim(owner_subject) <> ''),
    CONSTRAINT chk_workflow_run_code_not_blank CHECK (btrim(workflow_code) <> ''),
    CONSTRAINT chk_workflow_run_version_not_blank CHECK (btrim(workflow_version) <> ''),
    CONSTRAINT chk_workflow_run_idempotency_not_blank CHECK (btrim(idempotency_key) <> ''),
    CONSTRAINT chk_workflow_run_input_fingerprint_not_blank CHECK (btrim(input_fingerprint) <> ''),
    CONSTRAINT chk_workflow_run_status CHECK (
        status IN ('queued', 'running', 'accepted', 'succeeded', 'failed', 'cancel_requested', 'cancelled')
    )
);

CREATE INDEX IF NOT EXISTS idx_workflow_run_owner_updated
    ON workflow_run(owner_subject, updated_at, id);

CREATE TABLE IF NOT EXISTS workflow_node_run (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES workflow_run(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    capability_code TEXT NOT NULL,
    max_attempts BIGINT NOT NULL,
    status TEXT NOT NULL,
    attempt_count BIGINT NOT NULL,
    execution_reference TEXT,
    result_summary TEXT,
    output_fingerprint TEXT,
    failure_code TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_workflow_node_run_node UNIQUE (run_id, node_id),
    CONSTRAINT chk_workflow_node_run_node_not_blank CHECK (btrim(node_id) <> ''),
    CONSTRAINT chk_workflow_node_run_capability_not_blank CHECK (btrim(capability_code) <> ''),
    CONSTRAINT chk_workflow_node_run_max_attempts_positive CHECK (max_attempts > 0),
    CONSTRAINT chk_workflow_node_run_attempt_range CHECK (attempt_count >= 0 AND attempt_count <= max_attempts),
    CONSTRAINT chk_workflow_node_run_status CHECK (
        status IN ('queued', 'running', 'accepted', 'succeeded', 'failed', 'cancel_requested', 'cancelled', 'skipped')
    )
);

CREATE INDEX IF NOT EXISTS idx_workflow_node_run_ready
    ON workflow_node_run(run_id, status);

CREATE TABLE IF NOT EXISTS workflow_event (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES workflow_run(id) ON DELETE CASCADE,
    sequence BIGINT NOT NULL,
    transition_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_workflow_event_sequence UNIQUE (run_id, sequence),
    CONSTRAINT uq_workflow_event_transition UNIQUE (run_id, transition_id),
    CONSTRAINT chk_workflow_event_sequence_positive CHECK (sequence > 0),
    CONSTRAINT chk_workflow_event_transition_not_blank CHECK (btrim(transition_id) <> ''),
    CONSTRAINT chk_workflow_event_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_workflow_event_run_sequence
    ON workflow_event(run_id, sequence);

CREATE TABLE IF NOT EXISTS workflow_command_receipt (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES workflow_run(id) ON DELETE CASCADE,
    command_type TEXT NOT NULL,
    command_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_workflow_command_receipt UNIQUE (run_id, command_type, command_id),
    CONSTRAINT chk_workflow_receipt_type_not_blank CHECK (btrim(command_type) <> ''),
    CONSTRAINT chk_workflow_receipt_id_not_blank CHECK (btrim(command_id) <> '')
);
