BEGIN;
CREATE TABLE IF NOT EXISTS copilot_audit_events (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), clinic_id UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE, thread_id UUID, patient_id UUID, actor_user_id UUID, action_type TEXT NOT NULL, result TEXT NOT NULL DEFAULT 'success', entity_type TEXT, entity_id UUID, before_data JSONB NOT NULL DEFAULT '{}'::jsonb, after_data JSONB NOT NULL DEFAULT '{}'::jsonb, metadata JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), CONSTRAINT copilot_audit_action_not_blank CHECK (BTRIM(action_type) <> ''), CONSTRAINT copilot_audit_result_valid CHECK (result IN ('success','failed','prepared')));
CREATE INDEX IF NOT EXISTS copilot_audit_clinic_thread_created_idx ON copilot_audit_events (clinic_id,thread_id,created_at DESC);
CREATE INDEX IF NOT EXISTS copilot_audit_clinic_patient_created_idx ON copilot_audit_events (clinic_id,patient_id,created_at DESC);
COMMIT;
