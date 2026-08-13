BEGIN;

CREATE TABLE IF NOT EXISTS conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    clinic_id UUID NOT NULL
        REFERENCES clinics(id)
        ON DELETE CASCADE,

    thread_id UUID NOT NULL
        REFERENCES conversation_threads(id)
        ON DELETE CASCADE,

    patient_id UUID
        REFERENCES patients(id)
        ON DELETE SET NULL,

    sent_by_user_id UUID
        REFERENCES users(id)
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

    direction TEXT NOT NULL
        CHECK (
            direction IN (
                'inbound',
                'outbound'
            )
        ),

    author_type TEXT NOT NULL
        CHECK (
            author_type IN (
                'patient',
                'ai',
                'human',
                'system'
            )
        ),

    message_type TEXT NOT NULL DEFAULT 'text'
        CHECK (
            message_type IN (
                'text',
                'image',
                'audio',
                'video',
                'document',
                'location',
                'system'
            )
        ),

    body TEXT,

    external_id TEXT,

    provider TEXT,

    status TEXT NOT NULL DEFAULT 'received'
        CHECK (
            status IN (
                'received',
                'prepared',
                'sent',
                'delivered',
                'read',
                'failed'
            )
        ),

    requires_validation BOOLEAN NOT NULL DEFAULT FALSE,

    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT conversation_messages_body_required
        CHECK (
            message_type <> 'text'
            OR (
                body IS NOT NULL
                AND BTRIM(body) <> ''
            )
        ),

    CONSTRAINT conversation_messages_external_id_not_empty
        CHECK (
            external_id IS NULL
            OR BTRIM(external_id) <> ''
        ),

    CONSTRAINT conversation_messages_provider_not_empty
        CHECK (
            provider IS NULL
            OR BTRIM(provider) <> ''
        ),

    CONSTRAINT conversation_messages_human_author_consistency
        CHECK (
            author_type = 'human'
            OR sent_by_user_id IS NULL
        ),

    CONSTRAINT conversation_messages_inbound_author_consistency
        CHECK (
            direction <> 'inbound'
            OR author_type IN (
                'patient',
                'system'
            )
        ),

    CONSTRAINT conversation_messages_outbound_author_consistency
        CHECK (
            direction <> 'outbound'
            OR author_type IN (
                'ai',
                'human',
                'system'
            )
        )
);

CREATE INDEX IF NOT EXISTS
idx_conversation_messages_thread_history
ON conversation_messages (
    clinic_id,
    thread_id,
    occurred_at ASC,
    id ASC
);

CREATE INDEX IF NOT EXISTS
idx_conversation_messages_recent
ON conversation_messages (
    clinic_id,
    occurred_at DESC
);

CREATE INDEX IF NOT EXISTS
idx_conversation_messages_patient
ON conversation_messages (
    clinic_id,
    patient_id,
    occurred_at DESC
)
WHERE patient_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS
idx_conversation_messages_status
ON conversation_messages (
    clinic_id,
    status,
    occurred_at DESC
);

CREATE INDEX IF NOT EXISTS
idx_conversation_messages_validation
ON conversation_messages (
    clinic_id,
    requires_validation,
    occurred_at DESC
)
WHERE requires_validation = TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS
uq_conversation_messages_provider_external_id
ON conversation_messages (
    clinic_id,
    provider,
    external_id
)
WHERE
    provider IS NOT NULL
    AND external_id IS NOT NULL;

COMMIT;
