from datetime import date, datetime
from uuid import UUID
from psycopg.types.json import Jsonb

def _json_safe(value):
    if isinstance(value, (datetime, date)): return value.isoformat()
    if isinstance(value, UUID): return str(value)
    if isinstance(value, dict): return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [_json_safe(v) for v in value]
    return value

async def latest_thread_id_for_patient(*, cur, clinic_id: UUID, patient_id: UUID | None):
    if patient_id is None: return None
    await cur.execute("""SELECT id FROM conversation_threads WHERE clinic_id=%s AND patient_id=%s ORDER BY last_message_at DESC NULLS LAST, updated_at DESC LIMIT 1""", (clinic_id, patient_id))
    row = await cur.fetchone()
    return row["id"] if row else None

async def record_copilot_audit_event(*, cur, clinic_id: UUID, action_type: str, result: str = "success", thread_id: UUID | None = None, patient_id: UUID | None = None, actor_user_id: UUID | None = None, entity_type: str | None = None, entity_id: UUID | None = None, before_data: dict | None = None, after_data: dict | None = None, metadata: dict | None = None):
    if thread_id is None and patient_id is not None:
        thread_id = await latest_thread_id_for_patient(cur=cur, clinic_id=clinic_id, patient_id=patient_id)
    await cur.execute("""INSERT INTO copilot_audit_events (clinic_id,thread_id,patient_id,actor_user_id,action_type,result,entity_type,entity_id,before_data,after_data,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, created_at""", (clinic_id,thread_id,patient_id,actor_user_id,action_type,result,entity_type,entity_id,Jsonb(_json_safe(before_data or {})),Jsonb(_json_safe(after_data or {})),Jsonb(_json_safe(metadata or {}))))
    return await cur.fetchone()

async def list_copilot_audit_events(*, cur, clinic_id: UUID, thread_id: UUID, limit: int = 50):
    await cur.execute("""SELECT id,clinic_id,thread_id,patient_id,actor_user_id,action_type,result,entity_type,entity_id,before_data,after_data,metadata,created_at FROM copilot_audit_events WHERE clinic_id=%s AND thread_id=%s ORDER BY created_at DESC LIMIT %s""", (clinic_id,thread_id,limit))
    return await cur.fetchall()
