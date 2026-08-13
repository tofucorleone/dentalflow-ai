CREATE TABLE IF NOT EXISTS appointment_confirmation_reminders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    clinic_id uuid NOT NULL
        REFERENCES clinics(id)
        ON DELETE CASCADE,

    appointment_id uuid NOT NULL
        REFERENCES appointments(id)
        ON DELETE CASCADE,

    patient_id uuid NOT NULL
        REFERENCES patients(id)
        ON DELETE CASCADE,

    provider text NOT NULL DEFAULT 'evolution',

    provider_instance text NOT NULL,

    patient_phone text NOT NULL,

    status text NOT NULL DEFAULT 'pending',

    scheduled_for timestamp with time zone NOT NULL,

    sent_at timestamp with time zone,

    confirmed_at timestamp with time zone,

    external_message_id text,

    patient_reply text,

    error_message text,

    created_at timestamp with time zone NOT NULL DEFAULT NOW(),

    updated_at timestamp with time zone NOT NULL DEFAULT NOW(),

    CONSTRAINT appointment_confirmation_reminders_status_check
        CHECK (
            status IN (
                'pending',
                'sending',
                'sent',
                'confirmed',
                'failed',
                'cancelled'
            )
        ),

    CONSTRAINT appointment_confirmation_reminders_appointment_key
        UNIQUE (appointment_id)
);

CREATE INDEX IF NOT EXISTS idx_appointment_confirmation_reminders_due
    ON appointment_confirmation_reminders (
        status,
        scheduled_for
    );

CREATE INDEX IF NOT EXISTS idx_appointment_confirmation_reminders_clinic
    ON appointment_confirmation_reminders (
        clinic_id,
        appointment_id
    );
