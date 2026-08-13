from uuid import UUID

from app.ai.slot_filter import filter_suggested_slots
from app.ai.time_preferences import parse_time_preference


DR_MARTIN_ID = UUID(
    "42956ebb-7292-49ce-a31d-f8b591c197c4"
)
DR_SARA_ID = UUID(
    "21d8f93f-ae1b-4296-9ada-fea6ebc5d4d8"
)


SLOTS = [
    {
        "practitioner_id": str(DR_MARTIN_ID),
        "practitioner_name": "Dr Martin",
        "start_at": "2026-08-03T16:30:00+01:00",
        "end_at": "2026-08-03T17:00:00+01:00",
        "date_label": "03/08/2026",
        "time_label": "16h30",
    },
    {
        "practitioner_id": str(DR_SARA_ID),
        "practitioner_name": "Dr Sara",
        "start_at": "2026-08-03T17:30:00+01:00",
        "end_at": "2026-08-03T18:00:00+01:00",
        "date_label": "03/08/2026",
        "time_label": "17h30",
    },
    {
        "practitioner_id": str(DR_SARA_ID),
        "practitioner_name": "Dr Sara",
        "start_at": "2026-08-04T09:00:00+01:00",
        "end_at": "2026-08-04T09:30:00+01:00",
        "date_label": "04/08/2026",
        "time_label": "09h00",
    },
]


def test_filter_by_practitioner():
    result = filter_suggested_slots(
        SLOTS,
        practitioner_id=DR_SARA_ID,
    )

    assert len(result) == 2
    assert all(
        slot["practitioner_id"] == str(DR_SARA_ID)
        for slot in result
    )


def test_filter_by_numeric_date():
    result = filter_suggested_slots(
        SLOTS,
        date_text="04/08/2026",
    )

    assert len(result) == 1
    assert result[0]["time_label"] == "09h00"


def test_filter_by_iso_date():
    result = filter_suggested_slots(
        SLOTS,
        date_text="2026-08-03",
    )

    assert len(result) == 2


def test_filter_by_exact_time():
    result = filter_suggested_slots(
        SLOTS,
        preference=parse_time_preference("17h30"),
    )

    assert len(result) == 1
    assert result[0]["practitioner_name"] == "Dr Sara"


def test_filter_by_time_range():
    result = filter_suggested_slots(
        SLOTS,
        preference=parse_time_preference("après 17h"),
    )

    assert len(result) == 1
    assert result[0]["time_label"] == "17h30"


def test_combine_practitioner_date_and_time():
    result = filter_suggested_slots(
        SLOTS,
        practitioner_id=DR_SARA_ID,
        date_text="03/08/2026",
        preference=parse_time_preference("17h30"),
    )

    assert len(result) == 1
    assert result[0]["practitioner_name"] == "Dr Sara"
    assert result[0]["time_label"] == "17h30"


def test_invalid_slot_is_ignored():
    result = filter_suggested_slots(
        [
            *SLOTS,
            {
                "practitioner_id": str(DR_SARA_ID),
                "start_at": "date-invalide",
            },
        ],
        preference=parse_time_preference("17h30"),
    )

    assert len(result) == 1
    assert result[0]["time_label"] == "17h30"
