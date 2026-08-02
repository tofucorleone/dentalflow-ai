BEGIN;

ALTER TABLE patient_documents
ADD COLUMN IF NOT EXISTS ai_summary TEXT;

CREATE INDEX IF NOT EXISTS idx_patient_documents_ai_summary
ON patient_documents (clinic_id, patient_id)
WHERE ai_summary IS NOT NULL;

COMMIT;
