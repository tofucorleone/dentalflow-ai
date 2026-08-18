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
    hydrate_prepared_appointment_message_drafts,
    hydrate_prepared_recall_drafts,
    merge_task_states,
)


def build_appointment_message_actions(
    *,
    appointments: list[dict],
    now: datetime,
    sent_confirmation_appointment_ids: set | None = None,
    confirmation_status_by_appointment: dict | None = None,
) -> list[dict]:
    """
    Construit les tâches individuelles de communication patient :
    - confirmation de rendez-vous à J-1 ;
    - suivi après rendez-vous marqué no_show.

    Cette fonction est pure et ne déclenche aucun envoi.
    """

    actions: list[dict] = []
    sent_confirmation_ids = (
        sent_confirmation_appointment_ids or set()
    )
    confirmation_statuses = (
        confirmation_status_by_appointment or {}
    )

    for appointment in appointments:
        appointment_id = appointment.get("id")
        patient_id = appointment.get("patient_id")
        patient_name = (
            appointment.get("patient_name")
            or "Patient"
        )
        appointment_status = appointment.get("status")
        start_at = appointment.get("start_at")

        if (
            appointment_id is None
            or patient_id is None
            or start_at is None
        ):
            continue

        confirmation_status = (
            confirmation_statuses.get(
                appointment_id
            )
        )

        if (
            start_at.date()
            == (now + timedelta(days=1)).date()
            and (
                appointment_status == "pending"
                or (
                    appointment_status == "confirmed"
                    and confirmation_status
                    == "confirmed"
                )
            )
        ):
            confirmation_already_sent = (
                appointment_id in sent_confirmation_ids
            )

            draft_message = (
                f"Bonjour {patient_name}, "
                "nous vous rappelons votre rendez-vous demain. "
                "Merci de répondre OUI pour confirmer "
                "votre rendez-vous."
            )

            actions.append(
                {
                    "id": f"confirmation:{appointment_id}",
                    "type": "pending_confirmation",
                    "priority": "medium",
                    "score": 80,
                    "title": (
                        f"Confirmer le rendez-vous de "
                        f"{patient_name}"
                    ),
                    "description": (
                        "Le rendez-vous est prévu demain "
                        "et attend une confirmation patient."
                    ),
                    "recommended_action": (
                        "Préparer et valider le message "
                        "de confirmation WhatsApp."
                    ),
                    "patient_id": patient_id,
                    "appointment_id": appointment_id,
                    "draft_message": draft_message,
                    "reasons": [
                        "Rendez-vous prévu demain",
                        "Confirmation patient requise",
                    ],
                    "actions": [
                        {
                            "type": "navigate",
                            "label": "Ouvrir le calendrier",
                            "href": "/appointments",
                        }
                    ],
                    "requires_validation": (
                        not confirmation_already_sent
                    ),
                    "status": (
                        "completed"
                        if confirmation_already_sent
                        else "open"
                    ),
                    "confirmation_status": (
                        confirmation_status
                    ),
                }
            )

            continue

        if appointment_status == "no_show":
            draft_message = (
                f"Bonjour {patient_name}, "
                "nous avons constaté que vous n'avez pas pu "
                "vous présenter à votre rendez-vous. "
                "Souhaitez-vous convenir d'un nouveau créneau ?"
            )

            actions.append(
                {
                    "id": f"no_show:{appointment_id}",
                    "type": "no_show",
                    "priority": "high",
                    "score": 95,
                    "title": (
                        f"Recontacter {patient_name} "
                        "après son rendez-vous manqué"
                    ),
                    "description": (
                        "Le rendez-vous a été marqué absent."
                    ),
                    "recommended_action": (
                        "Préparer et valider un message "
                        "de suivi WhatsApp."
                    ),
                    "patient_id": patient_id,
                    "appointment_id": appointment_id,
                    "draft_message": draft_message,
                    "reasons": [
                        "Rendez-vous marqué no_show",
                    ],
                    "actions": [
                        {
                            "type": "navigate",
                            "label": "Ouvrir le calendrier",
                            "href": "/appointments",
                        }
                    ],
                    "requires_validation": True,
                }
            )

    return actions


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
    Construit uniquement les tâches de communication
    nécessitant une action opérationnelle :

    - confirmation patient à J-1 ;
    - suivi après rendez-vous no_show.

    Les confirmations déjà envoyées automatiquement
    ne sont pas proposées comme tâches.
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

    tomorrow_start = datetime.combine(
        local_now.date() + timedelta(days=1),
        time.min,
        tzinfo=timezone,
    )
    day_after_tomorrow = (
        tomorrow_start + timedelta(days=1)
    )

    await cur.execute(
        """
        SELECT
            a.id,
            a.clinic_id,
            a.patient_id,
            a.practitioner_id,
            a.treatment_id,
            a.channel,
            a.status,
            a.start_at,
            a.end_at,
            p.full_name AS patient_name,
            p.phone AS patient_phone,
            pr.full_name AS practitioner_name,
            t.name AS treatment_name
        FROM appointments a
        JOIN patients p
          ON p.id = a.patient_id
         AND p.clinic_id = a.clinic_id
        LEFT JOIN practitioners pr
          ON pr.id = a.practitioner_id
         AND pr.clinic_id = a.clinic_id
        LEFT JOIN treatments t
          ON t.id = a.treatment_id
         AND t.clinic_id = a.clinic_id
        WHERE a.clinic_id = %s
          AND (
              (
                  a.status = 'pending'
                  AND a.start_at >= %s
                  AND a.start_at < %s
              )
              OR a.status = 'no_show'
                OR (
                    a.status = 'confirmed'
                    AND a.start_at >= %s
                    AND a.start_at < %s
                    AND EXISTS (
                        SELECT 1
                        FROM appointment_confirmation_reminders acr
                        WHERE acr.clinic_id = a.clinic_id
                          AND acr.appointment_id = a.id
                          AND acr.status = 'confirmed'
                    )
                )
          )
        ORDER BY
            CASE
                WHEN a.status = 'no_show' THEN 0
                ELSE 1
            END,
            a.start_at DESC
        LIMIT 500
        """,
        (
            clinic_id,
            tomorrow_start,
            day_after_tomorrow,
            tomorrow_start,
            day_after_tomorrow,
        ),
    )

    appointments = await cur.fetchall()

    await cur.execute(
        """
        SELECT
            appointment_id,
            status
        FROM appointment_confirmation_reminders
        WHERE clinic_id = %s
          AND status IN ('sent', 'confirmed')
        """,
        (clinic_id,),
    )

    sent_confirmation_rows = await cur.fetchall()

    sent_confirmation_appointment_ids = {
        row["appointment_id"]
        for row in sent_confirmation_rows
    }

    confirmation_status_by_appointment = {
        row["appointment_id"]: row["status"]
        for row in sent_confirmation_rows
    }

    actions = build_appointment_message_actions(
        appointments=appointments,
        now=local_now,
        sent_confirmation_appointment_ids=(
            sent_confirmation_appointment_ids
        ),
        confirmation_status_by_appointment=(
            confirmation_status_by_appointment
        ),
    )

    tasks = build_tasks(
        recommended_actions=actions,
    )

    tasks = await merge_task_states(
        cur=cur,
        clinic_id=clinic_id,
        tasks=tasks,
    )

    return await hydrate_prepared_appointment_message_drafts(
        cur=cur,
        clinic_id=clinic_id,
        tasks=tasks,
    )

