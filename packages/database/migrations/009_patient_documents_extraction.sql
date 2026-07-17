BEGIN;

ALTER TABLE patient_documents
    ADD COLUMN IF NOT EXISTS extracted_text TEXT,
    ADD COLUMN IF NOT EXISTS extraction_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMPTZ;

ALTER TABLE patient_documents
    DROP CONSTRAINT IF EXISTS patient_documents_extraction_status_check;

ALTER TABLE patient_documents
    ADD CONSTRAINT patient_documents_extraction_status_check
    CHECK (
        extraction_status IN (
            'pending',
            'completed',
            'requires_ocr',
            'failed'
        )
    );

CREATE INDEX IF NOT EXISTS idx_patient_documents_extraction_status
    ON patient_documents(
        clinic_id,
        patient_id,
        extraction_status
    );

COMMIT;
