import asyncio
from datetime import datetime, timezone
from uuid import uuid4


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


def test_list_appointments_for_period_filters_clinic_and_dates():
    from app.appointment_service import list_appointments_for_period

    clinic_id = uuid4()
    date_from = datetime(2026, 8, 4, 0, 0, tzinfo=timezone.utc)
    date_to = datetime(2026, 8, 5, 0, 0, tzinfo=timezone.utc)

    expected_rows = [
        {
            "id": uuid4(),
            "clinic_id": clinic_id,
            "patient_id": uuid4(),
            "patient_name": "Patient Test",
            "patient_phone": "+213555000001",
            "practitioner_id": uuid4(),
            "practitioner_name": "Dr Sara",
            "treatment_id": uuid4(),
            "treatment_name": "Consultation",
            "channel": "dashboard",
            "status": "confirmed",
            "start_at": date_from,
            "end_at": date_from,
            "notes": None,
            "created_at": date_from,
            "updated_at": date_from,
        }
    ]

    cursor = FakeCursor(expected_rows)

    result = asyncio.run(
        list_appointments_for_period(
            cur=cursor,
            clinic_id=clinic_id,
            date_from=date_from,
            date_to=date_to,
            limit=100,
        )
    )

    assert result == expected_rows
    assert "FROM appointments a" in cursor.executed_query
    assert "WHERE a.clinic_id = %s" in cursor.executed_query
    assert "AND a.start_at >= %s" in cursor.executed_query
    assert "AND a.start_at < %s" in cursor.executed_query
    assert "ORDER BY a.start_at" in cursor.executed_query
    assert cursor.executed_params == (
        clinic_id,
        date_from,
        date_to,
        100,
    )
