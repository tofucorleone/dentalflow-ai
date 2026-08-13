from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.copilot.service import build_released_slots


def test_build_released_slots_from_cancelled_appointments():
    appointment_1 = uuid4()
    appointment_2 = uuid4()
    practitioner_1 = uuid4()
    patient_1 = uuid4()
    patient_2 = uuid4()

    appointments = [
        {
            "id": appointment_2,
            "status": "cancelled",
            "start_at": datetime(
                2026,
                8,
                4,
                14,
                0,
                tzinfo=ZoneInfo("Africa/Algiers"),
            ),
            "end_at": datetime(
                2026,
                8,
                4,
                14,
                30,
                tzinfo=ZoneInfo("Africa/Algiers"),
            ),
            "patient_id": patient_2,
            "practitioner_id": None,
            "practitioner_name": None,
        },
        {
            "id": appointment_1,
            "status": "cancelled",
            "start_at": datetime(
                2026,
                8,
                4,
                9,
                0,
                tzinfo=ZoneInfo("Africa/Algiers"),
            ),
            "end_at": datetime(
                2026,
                8,
                4,
                9,
                30,
                tzinfo=ZoneInfo("Africa/Algiers"),
            ),
            "patient_id": patient_1,
            "practitioner_id": practitioner_1,
            "practitioner_name": "Dr Sara",
        },
        {
            "id": uuid4(),
            "status": "confirmed",
            "start_at": datetime(
                2026,
                8,
                4,
                10,
                0,
                tzinfo=ZoneInfo("Africa/Algiers"),
            ),
            "end_at": datetime(
                2026,
                8,
                4,
                10,
                30,
                tzinfo=ZoneInfo("Africa/Algiers"),
            ),
            "patient_id": uuid4(),
            "practitioner_id": practitioner_1,
            "practitioner_name": "Dr Sara",
        },
    ]

    result = build_released_slots(appointments=appointments)

    assert result == [
        {
            "appointment_id": appointment_1,
            "cancelled_patient_id": patient_1,
            "practitioner_id": practitioner_1,
            "practitioner_name": "Dr Sara",
            "treatment_id": None,
            "start_at": appointments[1]["start_at"],
            "end_at": appointments[1]["end_at"],
        },
        {
            "appointment_id": appointment_2,
            "cancelled_patient_id": patient_2,
            "practitioner_id": None,
            "practitioner_name": None,
            "treatment_id": None,
            "start_at": appointments[0]["start_at"],
            "end_at": appointments[0]["end_at"],
        },
    ]


def test_build_released_slots_returns_empty_list_without_cancellation():
    result = build_released_slots(
        appointments=[
            {
                "id": uuid4(),
                "status": "confirmed",
                "start_at": datetime(
                    2026,
                    8,
                    4,
                    10,
                    0,
                    tzinfo=ZoneInfo("Africa/Algiers"),
                ),
                "end_at": datetime(
                    2026,
                    8,
                    4,
                    10,
                    30,
                    tzinfo=ZoneInfo("Africa/Algiers"),
                ),
                "patient_id": uuid4(),
                "practitioner_id": None,
                "practitioner_name": None,
            }
        ]
    )

    assert result == []
