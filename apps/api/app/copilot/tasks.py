from typing import Any
from uuid import UUID


def _optional_uuid(
    value: str | UUID | None,
) -> UUID | None:
    if value is None:
        return None

    if isinstance(value, UUID):
        return value

    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _extract_entity_ids(
    recommendation: dict[str, Any],
) -> tuple[UUID | None, UUID | None]:
    recommendation_id = str(
        recommendation.get("id") or ""
    )

    patient_id: UUID | None = None
    appointment_id: UUID | None = None

    if recommendation_id.startswith("recall:"):
        patient_id = _optional_uuid(
            recommendation_id.removeprefix(
                "recall:"
            )
        )

    elif recommendation_id.startswith(
        "released_slot:"
    ):
        appointment_id = _optional_uuid(
            recommendation_id.removeprefix(
                "released_slot:"
            )
        )

    return patient_id, appointment_id


def build_task_from_recommendation(
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    patient_id, appointment_id = (
        _extract_entity_ids(recommendation)
    )

    task_type = str(
        recommendation.get("type")
        or "unknown"
    )
    title = str(
        recommendation.get("title")
        or "Action Copilote"
    )
    description = str(
        recommendation.get("description")
        or ""
    )

    navigation_actions = [
        {
            "type": action["type"],
            "label": action["label"],
            "href": action["href"],
        }
        for action in (
            recommendation.get("actions")
            or []
        )
        if (
            isinstance(action, dict)
            and action.get("type") == "navigate"
            and action.get("label")
            and action.get("href")
        )
    ]

    return {
        "id": str(
            recommendation.get("id")
            or f"{task_type}:{title}"
        ),
        "type": task_type,
        "priority": str(
            recommendation.get("priority")
            or "low"
        ),
        "score": int(
            recommendation.get("score")
            or 0
        ),
        "title": title,
        "description": description,
        "recommended_action": title,
        "patient_id": patient_id,
        "appointment_id": appointment_id,
        "status": "open",
        "requires_validation": bool(
            recommendation.get(
                "requires_validation",
                False,
            )
        ),
        "actions": navigation_actions,
    }


def build_tasks(
    *,
    recommended_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Transforme les recommandations du Planner en tâches
    homogènes.

    Cette couche est strictement en lecture seule.
    """

    tasks = [
        build_task_from_recommendation(
            recommendation
        )
        for recommendation in recommended_actions
    ]

    priority_order = {
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    tasks.sort(
        key=lambda task: (
            task["score"],
            priority_order.get(
                task["priority"],
                0,
            ),
            task["title"],
        ),
        reverse=True,
    )

    return tasks


async def merge_task_states(
    *,
    cur,
    clinic_id,
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not tasks:
        return tasks

    task_keys = [str(task["id"]) for task in tasks]

    await cur.execute(
        """
        SELECT
            task_key,
            status,
            assigned_user_id,
            snoozed_until,
            completed_at
        FROM copilot_task_states
        WHERE clinic_id = %s
          AND task_key = ANY(%s)
        """,
        (
            clinic_id,
            task_keys,
        ),
    )

    rows = await cur.fetchall()

    states = {
        str(row["task_key"]): row
        for row in rows
    }

    merged: list[dict[str, Any]] = []

    for task in tasks:
        item = dict(task)
        state = states.get(str(task["id"]))

        if state is not None:
            item["status"] = state["status"]
            item["assigned_user_id"] = state["assigned_user_id"]
            item["snoozed_until"] = state["snoozed_until"]
            item["completed_at"] = state["completed_at"]
        else:
            item["assigned_user_id"] = None
            item["snoozed_until"] = None
            item["completed_at"] = None

        if (
            item.get("status") == "snoozed"
            and item.get("snoozed_until") is not None
        ):
            from datetime import datetime, timezone

            snoozed_until = item["snoozed_until"]

            if snoozed_until.tzinfo is None:
                snoozed_until = snoozed_until.replace(
                    tzinfo=timezone.utc,
                )

            if snoozed_until > datetime.now(timezone.utc):
                continue

            item["status"] = "open"
            item["snoozed_until"] = None

        merged.append(item)

    return merged


async def upsert_task_state(
    *,
    cur,
    clinic_id,
    task_key: str,
    status: str,
    assigned_user_id=None,
    snoozed_until=None,
) -> dict[str, Any]:
    completed_at_sql = (
        "NOW()"
        if status == "completed"
        else "NULL"
    )

    await cur.execute(
        f"""
        INSERT INTO copilot_task_states (
            clinic_id,
            task_key,
            status,
            assigned_user_id,
            snoozed_until,
            completed_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            {completed_at_sql}
        )
        ON CONFLICT (clinic_id, task_key)
        DO UPDATE SET
            status = EXCLUDED.status,
            assigned_user_id = EXCLUDED.assigned_user_id,
            snoozed_until = EXCLUDED.snoozed_until,
            completed_at = {completed_at_sql},
            updated_at = NOW()
        RETURNING
            task_key,
            status,
            assigned_user_id,
            snoozed_until,
            completed_at,
            updated_at
        """,
        (
            clinic_id,
            task_key,
            status,
            assigned_user_id,
            snoozed_until,
        ),
    )

    return await cur.fetchone()
