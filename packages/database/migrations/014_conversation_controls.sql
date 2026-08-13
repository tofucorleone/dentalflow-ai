BEGIN;

CREATE TABLE IF NOT EXISTS conversation_controls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    clinic_id UUID NOT NULL
        REFERENCES clinics(id)
        ON DELETE CASCADE,

    patient_id UUID
        REFERENCES patients(id)
        ON DELETE SET NULL,

    channel TEXT NOT NULL
        CHECK (
            channel IN (
                'whatsapp',
                'phone',
                'email',
                'sms',
                'web'
            )
        ),

    sender_phone TEXT NOT NULL,

    mode TEXT NOT NULL DEFAULT 'ai_active'
        CHECK (
            mode IN (
                'ai_active',
                'human_active',
                'paused',
                'closed'
            )
        ),

    taken_over_by_user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    taken_over_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT conversation_controls_sender_phone_not_empty
        CHECK (BTRIM(sender_phone) <> ''),

    CONSTRAINT conversation_controls_human_owner_consistency
        CHECK (
            mode = 'human_active'
            OR taken_over_by_user_id IS NULL
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS
uq_conversation_controls_channel_sender
ON conversation_controls (
    clinic_id,
    channel,
    sender_phone
);

CREATE INDEX IF NOT EXISTS
idx_conversation_controls_patient
ON conversation_controls (
    clinic_id,
    patient_id,
    channel
)
WHERE patient_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS
idx_conversation_controls_mode
ON conversation_controls (
    clinic_id,
    mode,
    updated_at DESC
);

COMMIT;
