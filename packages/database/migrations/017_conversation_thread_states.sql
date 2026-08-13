BEGIN;

CREATE TABLE IF NOT EXISTS conversation_thread_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    clinic_id UUID NOT NULL
        REFERENCES clinics(id)
        ON DELETE CASCADE,

    thread_id UUID NOT NULL
        REFERENCES conversation_threads(id)
        ON DELETE CASCADE,

    session_id TEXT,

    state TEXT NOT NULL DEFAULT 'idle',

    context JSONB NOT NULL DEFAULT '{}'::jsonb,

    last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS
uq_conversation_thread_states_default_session
ON conversation_thread_states (
    clinic_id,
    thread_id
)
WHERE session_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS
uq_conversation_thread_states_named_session
ON conversation_thread_states (
    clinic_id,
    thread_id,
    session_id
)
WHERE session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS
idx_conversation_thread_states_lookup
ON conversation_thread_states (
    clinic_id,
    thread_id,
    session_id
);

COMMIT;
