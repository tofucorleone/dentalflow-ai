BEGIN;

CREATE TABLE IF NOT EXISTS conversation_threads (
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

    provider TEXT,

    provider_instance TEXT,

    external_thread_id TEXT,

    assigned_user_id UUID
        REFERENCES users(id)
        ON DELETE SET NULL,

    status TEXT NOT NULL DEFAULT 'open'
        CHECK (
            status IN (
                'open',
                'closed'
            )
        ),

    unread_count INTEGER NOT NULL DEFAULT 0
        CHECK (unread_count >= 0),

    last_message_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT conversation_threads_sender_phone_not_empty
        CHECK (BTRIM(sender_phone) <> ''),

    CONSTRAINT conversation_threads_provider_not_empty
        CHECK (
            provider IS NULL
            OR BTRIM(provider) <> ''
        ),

    CONSTRAINT conversation_threads_provider_instance_not_empty
        CHECK (
            provider_instance IS NULL
            OR BTRIM(provider_instance) <> ''
        ),

    CONSTRAINT conversation_threads_external_thread_not_empty
        CHECK (
            external_thread_id IS NULL
            OR BTRIM(external_thread_id) <> ''
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS
uq_conversation_threads_channel_sender
ON conversation_threads (
    clinic_id,
    channel,
    sender_phone
);

CREATE INDEX IF NOT EXISTS
idx_conversation_threads_patient
ON conversation_threads (
    clinic_id,
    patient_id,
    last_message_at DESC
)
WHERE patient_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS
idx_conversation_threads_inbox
ON conversation_threads (
    clinic_id,
    status,
    last_message_at DESC
);

CREATE INDEX IF NOT EXISTS
idx_conversation_threads_assigned_user
ON conversation_threads (
    clinic_id,
    assigned_user_id,
    last_message_at DESC
)
WHERE assigned_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS
idx_conversation_threads_unread
ON conversation_threads (
    clinic_id,
    unread_count,
    last_message_at DESC
)
WHERE unread_count > 0;

CREATE INDEX IF NOT EXISTS
idx_conversation_threads_provider_instance
ON conversation_threads (
    provider,
    provider_instance
)
WHERE provider_instance IS NOT NULL;

COMMIT;
