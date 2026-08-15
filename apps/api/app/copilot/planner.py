from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.appointment_service import (
    clinic_timezone,
    list_appointments_for_period,
)
from app.copilot.overdue_recall import (
    enrich_overdue_recall_patients,
    list_overdue_recall_patients,
)
from app.copilot.operational import (
    build_priorities,
    build_released_slots,
)

from app.copilot.tasks import (
    build_tasks,
    hydrate_prepared_recall_drafts,
    merge_task_states,
)


async def build_conversation_actions(
    *,
    cur,
    clinic_id,
) -> list[dict]:
    await cur.execute(
        """
        SELECT
            ct.id,
            ct.patient_id,
            ct.unread_count,
            COALESCE(
                NULLIF(BTRIM(p.full_name), ''),
                ct.sender_phone,
                'Conversation'
            ) AS display_name
        FROM conversation_threads ct
        LEFT JOIN patients p
            ON p.id = ct.patient_id
           AND p.clinic_id = ct.clinic_id
        WHERE ct.clinic_id = %s
          AND ct.status = 'open'
          AND ct.unread_count > 0
        ORDER BY ct.unread_count DESC, ct.updated_at DESC
        LIMIT 20
        """,
        (clinic_id,),
    )

    rows = await cur.fetchall()

    actions: list[dict] = []

    for row in rows:
        thread_id = row["id"]
        unread_count = int(row.get("unread_count") or 0)
        display_name = row.get("display_name") or "Conversation"

        priority = (
            "high"
            if unread_count >= 3
            else "medium"
        )

        score = min(
            95,
            70 + (unread_count * 5),
        )

        actions.append(
            {
                "id": f"conversation:{thread_id}",
                "type": "conversation_reply",
                "priority": priority,
                "score": score,
                "title": f"Répondre à {display_name}",
                "description": (
                    f"{unread_count} message"
                    f"{'s' if unread_count > 1 else ''} "
                    f"non lu"
                    f"{'s' if unread_count > 1 else ''}."
                ),
                "actions": [
                    {
                        "type": "navigate",
                        "label": "Ouvrir la conversation",
                        "href": (
                            f"/conversations?thread={thread_id}"
                        ),
                    }
                ],
                "requires_validation": False,
            }
        )

    return actions


def build_recommended_actions(
    *,
    priorities: dict,
    released_slots: list[dict],
    overdue_recall_patients: list[dict],
) -> list[dict]:
    """
    Transforme l'état opérationnel brut en actions ordonnées.

    Cette fonction ne modifie aucune donnée et ne déclenche
    aucune action externe.
    """

    actions: list[dict] = []

    for patient in overdue_recall_patients:
        patient_id = patient["patient_id"]
        patient_name = (
            patient.get("patient_name")
            or patient.get("phone")
            or "Patient sans nom"
        )
        reasons = patient.get("reasons") or []

        description = (
            reasons[0]
            if reasons
            else "Suivi préventif à programmer."
        )

        actions.append(
            {
                "id": f"recall:{patient_id}",
                "type": "recall",
                "priority": patient["priority"],
                "score": patient["score"],
                "title": (
                    f"Recontacter {patient_name}"
                ),
                "description": description,
                "recommended_action": (
                    f"Préparer un message de rappel pour "
                    f"{patient_name} avant tout envoi."
                ),
                "patient_id": patient_id,
                "appointment_id": None,
                "draft_message": patient.get(
                    "draft_message"
                ),
                "reasons": reasons,
                "actions": [
                    {
                        "type": "navigate",
                        "label": (
                            f"Ouvrir la fiche de "
                            f"{patient_name}"
                        ),
                        "href": (
                            f"/patients/{patient_id}"
                        ),
                    }
                ],
                "requires_validation": True,
            }
        )

    for slot in released_slots:
        appointment_id = slot["appointment_id"]
        practitioner_name = (
            slot.get("practitioner_name")
            or "un praticien"
        )
        start_at = slot.get("start_at")

        if start_at is not None:
            slot_label = start_at.strftime(
                "%H:%M"
            )
            description = (
                f"Un créneau est disponible à "
                f"{slot_label} avec "
                f"{practitioner_name}."
            )
        else:
            description = (
                "Un rendez-vous annulé a libéré "
                f"un créneau avec {practitioner_name}."
            )

        candidate_count = len(
            slot.get("recall_candidates") or []
        )

        if candidate_count > 0:
            description += (
                f" {candidate_count} candidat"
                f"{'s' if candidate_count > 1 else ''} "
                "compatible"
                f"{'s' if candidate_count > 1 else ''} "
                "ont été trouvés."
            )

        actions.append(
            {
                "id": (
                    f"released_slot:{appointment_id}"
                ),
                "type": "released_slot",
                "priority": "high",
                "score": 90,
                "title": (
                    "Examiner un créneau libéré"
                ),
                "description": description,
                "actions": [
                    {
                        "type": "navigate",
                        "label": "Ouvrir le calendrier",
                        "href": "/appointments",
                    }
                ],
                "requires_validation": False,
            }
        )

    late_active = int(
        priorities.get("late_active") or 0
    )

    if late_active > 0:
        actions.append(
            {
                "id": "appointments:late_active",
                "type": "late_active",
                "priority": "high",
                "score": 85,
                "title": (
                    f"Vérifier {late_active} rendez-vous "
                    f"actif"
                    f"{'s' if late_active > 1 else ''} "
                    "en retard"
                ),
                "description": (
                    f"{late_active} rendez-vous actif"
                    f"{'s' if late_active > 1 else ''} "
                    "a dépassé son heure de début."
                ),
                "actions": [
                    {
                        "type": "navigate",
                        "label": "Ouvrir le calendrier",
                        "href": "/appointments",
                    }
                ],
                "requires_validation": False,
            }
        )

    pending_confirmation = int(
        priorities.get(
            "pending_confirmation"
        )
        or 0
    )

    if pending_confirmation > 0:
        actions.append(
            {
                "id": (
                    "appointments:"
                    "pending_confirmation"
                ),
                "type": "pending_confirmation",
                "priority": "medium",
                "score": 70,
                "title": (
                    f"Confirmer "
                    f"{pending_confirmation} "
                    "rendez-vous"
                ),
                "description": (
                    f"{pending_confirmation} "
                    "rendez-vous "
                    f"{'sont' if pending_confirmation > 1 else 'est'} "
                    "encore en attente de confirmation."
                ),
                "actions": [
                    {
                        "type": "navigate",
                        "label": "Ouvrir le calendrier",
                        "href": "/appointments",
                    }
                ],
                "requires_validation": False,
            }
        )

    priority_order = {
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    actions.sort(
        key=lambda action: (
            action["score"],
            priority_order.get(
                action["priority"],
                0,
            ),
            action["title"],
        ),
        reverse=True,
    )

    return actions


async def build_planner(
    *,
    cur,
    clinic_id,
    now: datetime | None = None,
) -> dict:
    """
    Construit un état opérationnel en lecture seule.

    Le Planner :
    - observe les rendez-vous du jour ;
    - calcule les priorités existantes ;
    - détecte les créneaux libérés ;
    - récupère les patients à recontacter ;
    - n'effectue aucune écriture.
    """

    timezone_name = await clinic_timezone(
        cur,
        clinic_id,
    )
    timezone = ZoneInfo(timezone_name)

    local_now = (
        now.astimezone(timezone)
        if now is not None
        else datetime.now(timezone)
    )

    day_start = datetime.combine(
        local_now.date(),
        time.min,
        tzinfo=timezone,
    )
    day_end = day_start + timedelta(days=1)

    appointments = await list_appointments_for_period(
        cur=cur,
        clinic_id=clinic_id,
        date_from=day_start,
        date_to=day_end,
        limit=500,
    )

    priorities = build_priorities(
        appointments=appointments,
        now=local_now,
    )

    released_slots = build_released_slots(
        appointments=appointments,
    )

    raw_overdue_patients = (
        await list_overdue_recall_patients(
            cur=cur,
            clinic_id=clinic_id,
            now=local_now,
            minimum_months=12,
            limit=20,
        )
    )

    overdue_recall_patients = (
        enrich_overdue_recall_patients(
            patients=raw_overdue_patients,
            now=local_now,
        )
    )

    conversation_actions = await build_conversation_actions(
        cur=cur,
        clinic_id=clinic_id,
    )

    recommended_actions = (
        build_recommended_actions(
            priorities=priorities,
            released_slots=released_slots,
            overdue_recall_patients=(
                overdue_recall_patients
            ),
        )
        + conversation_actions
    )

    recommended_actions.sort(
        key=lambda action: (
            int(action.get("score") or 0),
            str(action.get("title") or ""),
        ),
        reverse=True,
    )

    # Couche d’abstraction préparant le futur
    # Copilot Action Center.
    #
    # Les tâches sont calculées mais ne sont pas encore
    # exposées dans la réponse de l’endpoint Planner.
    _tasks = build_tasks(
        recommended_actions=recommended_actions,
    )

    # Vérification défensive : chaque recommandation doit
    # produire exactement une tâche.
    if len(_tasks) != len(recommended_actions):
        raise RuntimeError(
            "Le nombre de tâches Copilote générées "
            "est incohérent."
        )

    return {
        "generated_at": local_now,
        "timezone": timezone_name,
        "clinic_id": clinic_id,
        "priorities": priorities,
        "recommended_actions": (
            recommended_actions
        ),
        "released_slots": released_slots,
        "overdue_recall_patients": (
            overdue_recall_patients
        ),
        "appointments": appointments,
    }

async def build_copilot_tasks(
    *,
    cur,
    clinic_id,
    now: datetime | None = None,
) -> list[dict]:
    """
    Construit la liste unifiée des tâches opérationnelles.

    Cette fonction réutilise le Planner et reste strictement
    en lecture seule.
    """

    planner = await build_planner(
        cur=cur,
        clinic_id=clinic_id,
        now=now,
    )

    tasks = build_tasks(
        recommended_actions=(
            planner.get("recommended_actions")
            or []
        ),
    )

    tasks = await merge_task_states(
        cur=cur,
        clinic_id=clinic_id,
        tasks=tasks,
    )

    return await hydrate_prepared_recall_drafts(
        cur=cur,
        clinic_id=clinic_id,
        tasks=tasks,
    )

