BEGIN;

ALTER TABLE clinics
    ADD COLUMN IF NOT EXISTS display_name TEXT,
    ADD COLUMN IF NOT EXISTS software_name TEXT NOT NULL DEFAULT 'DentalFlow AI';

UPDATE clinics
SET display_name = name
WHERE display_name IS NULL;

ALTER TABLE clinics
    ALTER COLUMN display_name SET NOT NULL;

COMMIT;
