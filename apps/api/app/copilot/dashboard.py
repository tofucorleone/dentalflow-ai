from uuid import UUID

from app.copilot.planner import build_planner


async def build_dashboard_overview(
    *,
    cur,
    clinic_id: UUID,
) -> dict:
    """Construit le résumé opérationnel du Dashboard Copilote.

    Lecture seule : aucune action métier n'est exécutée ici.
    """

    planner = await build_planner(
        cur=cur,
        clinic_id=clinic_id,
    )

    await cur.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE unread_count > 0
            ) AS unread_threads,
            COALESCE(
                SUM(unread_count),
                0
            ) AS unread_messages
        FROM conversation_threads
        WHERE clinic_id = %s
          AND status = 'open'
        """,
        (clinic_id,),
    )

    conversation_counts = await cur.fetchone() or {}

    priorities = planner.get("priorities") or {}
    recommended_actions = (
        planner.get("recommended_actions") or []
    )
    overdue_recall_patients = (
        planner.get("overdue_recall_patients") or []
    )
    released_slots = planner.get("released_slots") or []

    recommendations: list[dict] = []

    for action in recommended_actions[:3]:
        href = None

        for navigation in action.get("actions") or []:
            if (
                isinstance(navigation, dict)
                and navigation.get("type") == "navigate"
                and navigation.get("href")
            ):
                href = str(navigation["href"])
                break

        recommendations.append(
            {
                "id": str(action.get("id") or action.get("title") or "action"),
                "type": str(action.get("type") or "action"),
                "priority": str(action.get("priority") or "low"),
                "title": str(action.get("title") or "Action Copilote"),
                "description": str(action.get("description") or ""),
                "href": href,
            }
        )

    late_active = int(priorities.get("late_active") or 0)
    pending_confirmation = int(
        priorities.get("pending_confirmation") or 0
    )
    cancelled_today = int(
        priorities.get("cancelled_today") or 0
    )
    no_show = int(priorities.get("no_show") or 0)

    alerts = late_active + cancelled_today + no_show + len(released_slots)

    return {
        "generated_at": planner["generated_at"],
        "timezone": planner["timezone"],
        "clinic_id": clinic_id,
        "unread_messages": int(
            conversation_counts.get("unread_messages") or 0
        ),
        "unread_threads": int(
            conversation_counts.get("unread_threads") or 0
        ),
        "pending_confirmations": pending_confirmation,
        "patients_to_recall": len(overdue_recall_patients),
        "late_active": late_active,
        "released_slots": len(released_slots),
        "alerts": alerts,
        "recommendations": recommendations,
    }


__all__ = ["build_dashboard_overview"]
