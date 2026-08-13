from datetime import datetime
from zoneinfo import ZoneInfo

from app.copilot.service import build_priorities


def test_build_priorities():
    now = datetime(
        2026,
        8,
        4,
        10,
        0,
        tzinfo=ZoneInfo("Europe/Paris"),
    )

    appointments = [
        {
            "status": "pending",
            "start_at": datetime(
                2026,
                8,
                4,
                14,
                0,
                tzinfo=ZoneInfo("Europe/Paris"),
            ),
            "patient_name": "Alice",
        },
        {
            "status": "confirmed",
            "start_at": datetime(
                2026,
                8,
                4,
                9,
                0,
                tzinfo=ZoneInfo("Europe/Paris"),
            ),
            "patient_name": "Bob",
        },
        {
            "status": "cancelled",
            "start_at": datetime(
                2026,
                8,
                4,
                11,
                0,
                tzinfo=ZoneInfo("Europe/Paris"),
            ),
            "patient_name": "Charlie",
        },
        {
            "status": "no_show",
            "start_at": datetime(
                2026,
                8,
                4,
                8,
                30,
                tzinfo=ZoneInfo("Europe/Paris"),
            ),
            "patient_name": "David",
        },
    ]

    priorities = build_priorities(
        appointments=appointments,
        now=now,
    )

    assert priorities["pending_confirmation"] == 1
    assert priorities["cancelled_today"] == 1
    assert priorities["no_show"] == 1
    assert priorities["late_active"] == 1
