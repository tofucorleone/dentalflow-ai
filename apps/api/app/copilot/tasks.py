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

    patient_id = _optional_uuid(
        recommendation.get("patient_id")
    )
    appointment_id = _optional_uuid(
        recommendation.get("appointment_id")
    )

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

    elif recommendation_id.startswith(
        "confirmation:"
    ):
        appointment_id = _optional_uuid(
            recommendation_id.removeprefix(
                "confirmation:"
            )
        )

    elif recommendation_id.startswith(
        "no_show:"
    ):
        appointment_id = _optional_uuid(
            recommendation_id.removeprefix(
                "no_show:"
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
        "recommended_action": str(
            recommendation.get(
                "recommended_action"
            )
            or title
        ),
        "patient_id": patient_id,
        "appointment_id": appointment_id,
        "draft_message": recommendation.get(
            "draft_message"
        ),
        "reasons": list(
            recommendation.get("reasons")
            or []
        ),
        "status": str(
            recommendation.get("status")
            or "open"
        ),
        "confirmation_status": (
            recommendation.get(
                "confirmation_status"
            )
        ),
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


async def hydrate_prepared_appointment_message_drafts(
    *,
    cur,
    clinic_id,
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prepared_tasks = [
        task
        for task in tasks
        if (
            task.get("type")
            in {"pending_confirmation", "no_show"}
            and task.get("status") == "prepared"
            and task.get("patient_id") is not None
            and task.get("appointment_id") is not None
        )
    ]

    if not prepared_tasks:
        return tasks

    appointment_ids = list(
        {
            task["appointment_id"]
            for task in prepared_tasks
        }
    )

    await cur.execute(
        """
        SELECT DISTINCT ON (
            appointment_id,
            payload->>'message_kind'
        )
            id,
            patient_id,
            appointment_id,
            payload->>'message_kind' AS message_kind,
            payload->>'message' AS message
        FROM communication_events
        WHERE clinic_id = %s
          AND appointment_id = ANY(%s)
          AND event_type = 'appointment_message_draft'
          AND channel = 'whatsapp'
          AND direction = 'outbound'
          AND payload->>'status' = 'draft'
        ORDER BY
            appointment_id,
            payload->>'message_kind',
            created_at DESC,
            id DESC
        """,
        (
            clinic_id,
            appointment_ids,
        ),
    )

    rows = await cur.fetchall()

    drafts = {
        (
            row["appointment_id"],
            row["message_kind"],
        ): {
            "id": row["id"],
            "message": row["message"],
        }
        for row in rows
        if row.get("message")
    }

    hydrated: list[dict[str, Any]] = []

    for task in tasks:
        item = dict(task)

        if (
            item.get("type")
            in {"pending_confirmation", "no_show"}
            and item.get("status") == "prepared"
        ):
            draft = drafts.get(
                (
                    item.get("appointment_id"),
                    item.get("type"),
                )
            )

            if draft:
                item["draft_id"] = draft["id"]
                item["draft_message"] = draft["message"]

        hydrated.append(item)

    return hydrated


async def hydrate_prepared_recall_drafts(
    *,
    cur,
    clinic_id,
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prepared_recall_tasks = [
        task
        for task in tasks
        if (
            task.get("type") == "recall"
            and task.get("status") == "prepared"
            and task.get("patient_id") is not None
        )
    ]

    if not prepared_recall_tasks:
        return tasks

    patient_ids = list(
        {
            task["patient_id"]
            for task in prepared_recall_tasks
        }
    )

    await cur.execute(
        """
        SELECT DISTINCT ON (
            patient_id,
            appointment_id
        )
            id,
            patient_id,
            appointment_id,
            payload->>'message' AS message
        FROM communication_events
        WHERE clinic_id = %s
          AND patient_id = ANY(%s)
          AND event_type = 'recall_draft'
          AND channel = 'whatsapp'
          AND direction = 'outbound'
          AND payload->>'status' = 'draft'
        ORDER BY
            patient_id,
            appointment_id,
            created_at DESC,
            id DESC
        """,
        (
            clinic_id,
            patient_ids,
        ),
    )

    rows = await cur.fetchall()

    drafts = {
        (
            row["patient_id"],
            row["appointment_id"],
        ): {
            "id": row["id"],
            "message": row["message"],
        }
        for row in rows
        if row.get("message")
    }

    hydrated: list[dict[str, Any]] = []

    for task in tasks:
        item = dict(task)

        if (
            item.get("type") == "recall"
            and item.get("status") == "prepared"
        ):
            key = (
                item.get("patient_id"),
                item.get("appointment_id"),
            )

            draft = drafts.get(key)

            if draft:
                item["draft_id"] = draft["id"]
                item["draft_message"] = draft["message"]

        hydrated.append(item)

    return hydrated
