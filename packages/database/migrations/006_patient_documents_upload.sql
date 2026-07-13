BEGIN;

ALTER TABLE patient_documents
    ADD COLUMN IF NOT EXISTS original_filename TEXT,
    ADD COLUMN IF NOT EXISTS storage_path TEXT,
    ADD COLUMN IF NOT EXISTS uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE patient_documents
SET original_filename = filename
WHERE original_filename IS NULL;

UPDATE patient_documents
SET storage_path = storage_url
WHERE storage_path IS NULL;

ALTER TABLE patient_documents
    ALTER COLUMN original_filename SET NOT NULL,
    ALTER COLUMN storage_path SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_patient_documents_uploaded_by
    ON patient_documents(uploaded_by);

CREATE INDEX IF NOT EXISTS idx_patient_documents_type
    ON patient_documents(clinic_id, patient_id, document_type);

COMMIT;
