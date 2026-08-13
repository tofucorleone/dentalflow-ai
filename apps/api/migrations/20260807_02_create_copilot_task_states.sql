CREATE TABLE IF NOT EXISTS copilot_task_states (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id uuid NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    task_key text NOT NULL,
    status text NOT NULL DEFAULT 'open',
    assigned_user_id uuid NULL REFERENCES users(id) ON DELETE SET NULL,
    snoozed_until timestamptz NULL,
    completed_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT copilot_task_states_status_check
        CHECK (status IN ('open', 'completed', 'dismissed', 'snoozed')),

    CONSTRAINT copilot_task_states_task_key_not_blank
        CHECK (btrim(task_key) <> ''),

    CONSTRAINT copilot_task_states_clinic_task_unique
        UNIQUE (clinic_id, task_key)
);

CREATE INDEX IF NOT EXISTS copilot_task_states_clinic_status_idx
    ON copilot_task_states (clinic_id, status);

CREATE INDEX IF NOT EXISTS copilot_task_states_snoozed_until_idx
    ON copilot_task_states (snoozed_until);
