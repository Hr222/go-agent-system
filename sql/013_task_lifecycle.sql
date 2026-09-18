-- TM-02 Task 生命周期持久化。该脚本无历史 Task 可回填，允许安全重复执行。

CREATE TABLE IF NOT EXISTS task (
    id UUID PRIMARY KEY,
    task_type TEXT NOT NULL,
    owner_subject TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    max_attempts BIGINT NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    display_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    allow_manual_retry BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    cancel_requested_at TIMESTAMPTZ,
    result_summary TEXT,
    result_fingerprint TEXT,
    failure_code TEXT,
    CONSTRAINT uq_task_submission UNIQUE (owner_subject, task_type, idempotency_key),
    CONSTRAINT chk_task_type_not_blank CHECK (btrim(task_type) <> ''),
    CONSTRAINT chk_task_owner_not_blank CHECK (btrim(owner_subject) <> ''),
    CONSTRAINT chk_task_idempotency_not_blank CHECK (btrim(idempotency_key) <> ''),
    CONSTRAINT chk_task_input_fingerprint_not_blank CHECK (btrim(input_fingerprint) <> ''),
    CONSTRAINT chk_task_max_attempts_positive CHECK (max_attempts > 0),
    CONSTRAINT chk_task_status CHECK (
        status IN ('queued', 'running', 'retry_wait', 'cancel_requested', 'succeeded', 'failed', 'cancelled')
    ),
    CONSTRAINT chk_task_display_metadata_object CHECK (jsonb_typeof(display_metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_task_status_available_at
    ON task(status, available_at);

CREATE TABLE IF NOT EXISTS task_attempt (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    number BIGINT NOT NULL,
    worker_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    lease_token TEXT NOT NULL,
    lease_expires_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    renewal_sequence BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    failure_category TEXT,
    failure_code TEXT,
    result_fingerprint TEXT,
    CONSTRAINT uq_task_attempt_number UNIQUE (task_id, number),
    CONSTRAINT uq_task_attempt_claim UNIQUE (task_id, worker_id, claim_id),
    CONSTRAINT chk_task_attempt_number_positive CHECK (number > 0),
    CONSTRAINT chk_task_attempt_worker_not_blank CHECK (btrim(worker_id) <> ''),
    CONSTRAINT chk_task_attempt_claim_not_blank CHECK (btrim(claim_id) <> ''),
    CONSTRAINT chk_task_attempt_lease_not_blank CHECK (btrim(lease_token) <> ''),
    CONSTRAINT chk_task_attempt_lease_after_create CHECK (lease_expires_at > created_at),
    CONSTRAINT chk_task_attempt_status CHECK (
        status IN ('active', 'succeeded', 'failed', 'cancelled', 'expired')
    ),
    CONSTRAINT chk_task_attempt_renewal_sequence_nonnegative CHECK (renewal_sequence >= 0),
    CONSTRAINT chk_task_attempt_failure_category CHECK (
        failure_category IS NULL OR failure_category IN ('transient', 'permanent', 'lease_expired')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_task_attempt_one_active
    ON task_attempt(task_id)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_task_attempt_active_expiry
    ON task_attempt(lease_expires_at, task_id)
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS task_event (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    sequence BIGINT NOT NULL,
    transition_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_task_event_sequence UNIQUE (task_id, sequence),
    CONSTRAINT uq_task_event_transition UNIQUE (task_id, transition_id),
    CONSTRAINT chk_task_event_sequence_positive CHECK (sequence > 0),
    CONSTRAINT chk_task_event_transition_not_blank CHECK (btrim(transition_id) <> ''),
    CONSTRAINT chk_task_event_metadata_object CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT chk_task_event_type CHECK (
        event_type IN (
            'TASK_CREATED', 'TASK_CLAIMED', 'TASK_CANCEL_REQUESTED', 'TASK_CANCELLED',
            'TASK_SUCCEEDED', 'TASK_FAILED', 'TASK_RETRY_SCHEDULED', 'TASK_REQUEUED',
            'TASK_RETRY_REQUESTED', 'TASK_RECOVERED'
        )
    )
);

CREATE TABLE IF NOT EXISTS task_command_receipt (
    id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    command_type TEXT NOT NULL,
    command_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_task_command_receipt UNIQUE (task_id, command_type, command_id),
    CONSTRAINT chk_task_receipt_type_not_blank CHECK (btrim(command_type) <> ''),
    CONSTRAINT chk_task_receipt_id_not_blank CHECK (btrim(command_id) <> '')
);
