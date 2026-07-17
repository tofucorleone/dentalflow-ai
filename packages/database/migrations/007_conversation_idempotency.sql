BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_history_external_message
    ON conversation_history (
        clinic_id,
        channel,
        external_id
    )
    WHERE external_id IS NOT NULL;

COMMIT;
