CREATE TABLE IF NOT EXISTS treatment_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    clinic_id uuid NOT NULL
        REFERENCES clinics(id)
        ON DELETE CASCADE,

    treatment_id uuid NOT NULL
        REFERENCES treatments(id)
        ON DELETE CASCADE,

    position integer NOT NULL,

    name text NOT NULL,

    description text,

    duration_minutes integer NOT NULL,

    created_at timestamp with time zone NOT NULL DEFAULT NOW(),

    updated_at timestamp with time zone NOT NULL DEFAULT NOW(),

    CONSTRAINT treatment_sessions_position_check
        CHECK (position > 0),

    CONSTRAINT treatment_sessions_duration_check
        CHECK (duration_minutes > 0),

    CONSTRAINT treatment_sessions_treatment_position_key
        UNIQUE (treatment_id, position)
);

CREATE INDEX IF NOT EXISTS idx_treatment_sessions_clinic_treatment
    ON treatment_sessions (clinic_id, treatment_id);
