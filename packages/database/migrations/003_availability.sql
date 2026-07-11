BEGIN;

CREATE INDEX IF NOT EXISTS idx_appointments_active_overlap
ON appointments (
    clinic_id,
    practitioner_id,
    start_at,
    end_at
)
WHERE status IN ('pending', 'confirmed');

INSERT INTO practitioner_treatments (practitioner_id, treatment_id)
SELECT p.id, t.id
FROM practitioners p
JOIN treatments t ON t.clinic_id = p.clinic_id
WHERE p.active = TRUE
  AND t.active = TRUE
ON CONFLICT DO NOTHING;

COMMIT;
