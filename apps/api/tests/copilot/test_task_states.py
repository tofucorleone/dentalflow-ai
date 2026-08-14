import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.copilot.tasks import (
    merge_task_states,
    upsert_task_state,
)


class MergeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None

    async def execute(self, query, params):
        self.query = query
        self.params = params

    async def fetchall(self):
        return self.rows


class UpsertCursor:
    def __init__(self):
        self.query = None
        self.params = None
        self.row = None

    async def execute(self, query, params):
        self.query = query
        self.params = params

        self.row = {
            "task_key": params[1],
            "status": params[2],
            "assigned_user_id": params[3],
            "snoozed_until": params[4],
            "completed_at": (
                datetime.now(timezone.utc)
                if params[2] == "completed"
                else None
            ),
            "updated_at": datetime.now(timezone.utc),
        }

    async def fetchone(self):
        return self.row


def make_task(task_id="appointments:pending_confirmation"):
    return {
        "id": task_id,
        "type": "pending_confirmation",
        "priority": "medium",
        "score": 70,
        "title": "Confirmer un rendez-vous",
        "description": "Un rendez-vous attend une confirmation.",
        "recommended_action": "Confirmer un rendez-vous",
        "patient_id": None,
        "appointment_id": None,
        "status": "open",
        "requires_validation": False,
        "actions": [],
    }


def test_merge_task_states_keeps_assignment():
    clinic_id = uuid4()
    user_id = uuid4()
    task = make_task()

    cursor = MergeCursor(
        [
            {
                "task_key": task["id"],
                "status": "open",
                "assigned_user_id": user_id,
                "snoozed_until": None,
                "completed_at": None,
            }
        ]
    )

    result = asyncio.run(
        merge_task_states(
            cur=cursor,
            clinic_id=clinic_id,
            tasks=[task],
        )
    )

    assert len(result) == 1
    assert result[0]["status"] == "open"
    assert result[0]["assigned_user_id"] == user_id
    assert result[0]["snoozed_until"] is None


def test_merge_task_states_hides_future_snoozed_task():
    task = make_task()

    cursor = MergeCursor(
        [
            {
                "task_key": task["id"],
                "status": "snoozed",
                "assigned_user_id": None,
                "snoozed_until": (
                    datetime.now(timezone.utc)
                    + timedelta(hours=2)
                ),
                "completed_at": None,
            }
        ]
    )

    result = asyncio.run(
        merge_task_states(
            cur=cursor,
            clinic_id=uuid4(),
            tasks=[task],
        )
    )

    assert result == []


def test_merge_task_states_reopens_expired_snooze():
    task = make_task()

    cursor = MergeCursor(
        [
            {
                "task_key": task["id"],
                "status": "snoozed",
                "assigned_user_id": None,
                "snoozed_until": (
                    datetime.now(timezone.utc)
                    - timedelta(minutes=5)
                ),
                "completed_at": None,
            }
        ]
    )

    result = asyncio.run(
        merge_task_states(
            cur=cursor,
            clinic_id=uuid4(),
            tasks=[task],
        )
    )

    assert len(result) == 1
    assert result[0]["status"] == "open"
    assert result[0]["snoozed_until"] is None


def test_upsert_task_state_assigns_task():
    clinic_id = uuid4()
    user_id = uuid4()
    task_key = "appointments:pending_confirmation"

    cursor = UpsertCursor()

    result = asyncio.run(
        upsert_task_state(
            cur=cursor,
            clinic_id=clinic_id,
            task_key=task_key,
            status="open",
            assigned_user_id=user_id,
        )
    )

    assert "INSERT INTO copilot_task_states" in cursor.query
    assert "ON CONFLICT (clinic_id, task_key)" in cursor.query

    assert cursor.params == (
        clinic_id,
        task_key,
        "open",
        user_id,
        None,
    )

    assert result["task_key"] == task_key
    assert result["status"] == "open"
    assert result["assigned_user_id"] == user_id


def test_upsert_completed_task_sets_completed_at():
    cursor = UpsertCursor()

    result = asyncio.run(
        upsert_task_state(
            cur=cursor,
            clinic_id=uuid4(),
            task_key="appointments:pending_confirmation",
            status="completed",
        )
    )

    assert "NOW()" in cursor.query
    assert result["status"] == "completed"
    assert result["completed_at"] is not None
