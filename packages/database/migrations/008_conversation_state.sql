BEGIN;

CREATE TABLE IF NOT EXISTS conversation_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    clinic_id UUID NOT NULL
        REFERENCES clinics(id)
        ON DELETE CASCADE,

    patient_id UUID NOT NULL
        REFERENCES patients(id)
        ON DELETE CASCADE,

    channel TEXT NOT NULL
        CHECK (channel IN ('whatsapp', 'phone', 'email', 'sms', 'web')),

    state TEXT NOT NULL DEFAULT 'idle',

    last_intent TEXT,

    context JSONB NOT NULL DEFAULT '{}'::jsonb,

    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (
        clinic_id,
        patient_id,
        channel
    )
);

CREATE INDEX IF NOT EXISTS idx_conversation_states_lookup
    ON conversation_states (
        clinic_id,
        patient_id,
        channel
    );

CREATE INDEX IF NOT EXISTS idx_conversation_states_expiration
    ON conversation_states (expires_at)
    WHERE expires_at IS NOT NULL;

COMMIT;
