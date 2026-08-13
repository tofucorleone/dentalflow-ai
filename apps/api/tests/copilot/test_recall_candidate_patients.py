import asyncio
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo


class FakeCursor:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.executed_query = None
        self.executed_params = None

    async def execute(self, query, params=None):
        self.executed_query = " ".join(query.split())
        self.executed_params = params

    async def fetchall(self):
        return self.rows


def test_list_recall_candidate_patients_filters_and_prepares_rows():
    from app.copilot.service import list_recall_candidate_patients

    clinic_id = uuid4()
    cancelled_patient_id = uuid4()
    practitioner_id = uuid4()

    slot_start = datetime(
        2026,
        8,
        4,
        9,
        0,
        tzinfo=ZoneInfo("Africa/Algiers"),
    )
    slot_end = datetime(
        2026,
        8,
        4,
        9,
        30,
        tzinfo=ZoneInfo("Africa/Algiers"),
    )

    expected_rows = [
        {
            "patient_id": uuid4(),
            "patient_name": "Patient Test",
            "active": True,
            "preferred_practitioner_id": practitioner_id,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
                "preferred_day": "mardi",
            },
            "last_goal": "Cherche un rendez-vous.",
            "has_active_overlap": False,
        }
    ]

    cursor = FakeCursor(expected_rows)

    result = asyncio.run(
        list_recall_candidate_patients(
            cur=cursor,
            clinic_id=clinic_id,
            cancelled_patient_id=cancelled_patient_id,
            slot_start=slot_start,
            slot_end=slot_end,
            limit=100,
        )
    )

    assert result == expected_rows

    assert "FROM patients p" in cursor.executed_query
    assert "LEFT JOIN patient_ai_memory m" in cursor.executed_query
    assert "WHERE p.clinic_id = %s" in cursor.executed_query
    assert "AND p.active = TRUE" in cursor.executed_query
    assert "AND p.id <> %s" in cursor.executed_query
    assert "FROM appointments a" in cursor.executed_query
    assert "a.status IN ('pending', 'confirmed')" in cursor.executed_query
    assert "a.start_at < %s" in cursor.executed_query
    assert "a.end_at > %s" in cursor.executed_query

    assert cursor.executed_params == (
        slot_end,
        slot_start,
        clinic_id,
        cancelled_patient_id,
        100,
    )
