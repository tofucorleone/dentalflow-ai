CREATE INDEX IF NOT EXISTS
    communication_events_active_recall_drafts_idx
ON communication_events (
    clinic_id,
    patient_id,
    appointment_id,
    created_at DESC
)
WHERE event_type = 'recall_draft'
  AND channel = 'whatsapp'
  AND direction = 'outbound'
  AND payload->>'status' = 'draft';
