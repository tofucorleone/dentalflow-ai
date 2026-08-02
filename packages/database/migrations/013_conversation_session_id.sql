BEGIN;

ALTER TABLE conversation_states
ADD COLUMN IF NOT EXISTS session_id TEXT;

ALTER TABLE conversation_states
DROP CONSTRAINT IF EXISTS
conversation_states_clinic_id_patient_id_channel_key;

DROP INDEX IF EXISTS idx_conversation_states_lookup;

CREATE UNIQUE INDEX IF NOT EXISTS
uq_conversation_states_default_session
ON conversation_states (
    clinic_id,
    patient_id,
    channel
)
WHERE session_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS
uq_conversation_states_named_session
ON conversation_states (
    clinic_id,
    patient_id,
    channel,
    session_id
)
WHERE session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS
idx_conversation_states_lookup
ON conversation_states (
    clinic_id,
    patient_id,
    channel,
    session_id
);

COMMIT;
