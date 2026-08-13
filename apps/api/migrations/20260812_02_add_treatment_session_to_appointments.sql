ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS treatment_session_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'appointments_treatment_session_id_fkey'
    ) THEN
        ALTER TABLE appointments
            ADD CONSTRAINT appointments_treatment_session_id_fkey
            FOREIGN KEY (treatment_session_id)
            REFERENCES treatment_sessions(id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_appointments_treatment_session
    ON appointments (
        clinic_id,
        treatment_id,
        treatment_session_id
    );
