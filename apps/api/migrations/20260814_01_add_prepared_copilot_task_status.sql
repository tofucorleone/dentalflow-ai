ALTER TABLE copilot_task_states
    DROP CONSTRAINT IF EXISTS copilot_task_states_status_check;

ALTER TABLE copilot_task_states
    ADD CONSTRAINT copilot_task_states_status_check
    CHECK (
        status IN (
            'open',
            'prepared',
            'completed',
            'dismissed',
            'snoozed'
        )
    );
