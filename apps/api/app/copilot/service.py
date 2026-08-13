from datetime import datetime, time, timedelta
import unicodedata
import re
from uuid import UUID
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb

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

from app.copilot.tools.patient import (
    answer_patient_lookup,
    extract_patient_search_query,
    search_copilot_patients,
)

from app.copilot.tools.practitioner import (
    answer_next_practitioner_appointment,
    extract_practitioner_search_query,
    get_next_practitioner_appointment,
    looks_like_next_practitioner_appointment,
    search_copilot_practitioners,
)

from app.copilot.tools.registry import (
    execute_copilot_tool,
    find_copilot_tool,
)

from app.copilot.tools.response import (
    build_copilot_response,
)



async def list_recall_candidate_patients(
    *,
    cur,
    clinic_id: UUID,
    cancelled_patient_id: UUID,
    slot_start: datetime,
    slot_end: datetime,
    limit: int = 100,
) -> list[dict]:
    safe_limit = min(max(limit, 1), 500)

    await cur.execute(
        """
        SELECT
            p.id AS patient_id,
            p.full_name AS patient_name,
            p.active,
            p.preferred_practitioner_id,
            COALESCE(m.preferences, '{}'::jsonb) AS preferences,
            m.last_goal,
            EXISTS (
                SELECT 1
                FROM appointments a
                WHERE a.clinic_id = p.clinic_id
                  AND a.patient_id = p.id
                  AND a.status IN ('pending', 'confirmed')
                  AND a.start_at < %s
                  AND a.end_at > %s
            ) AS has_active_overlap
        FROM patients p
        LEFT JOIN patient_ai_memory m
          ON m.patient_id = p.id
         AND m.clinic_id = p.clinic_id
        WHERE p.clinic_id = %s
          AND p.active = TRUE
          AND p.id <> %s
        ORDER BY p.updated_at DESC, p.full_name
        LIMIT %s
        """,
        (
            slot_end,
            slot_start,
            clinic_id,
            cancelled_patient_id,
            safe_limit,
        ),
    )

    return await cur.fetchall()


def _normalize_match_text(value: str | None) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize(
        "NFKD",
        value.strip().lower(),
    )

    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )



def _preferred_time_matches(
    preferred_time: str,
    slot_start: datetime,
) -> bool:
    normalized = _normalize_match_text(preferred_time)

    if normalized == "matin":
        return slot_start.hour < 12

    if normalized in {"apres-midi", "apres midi"}:
        return 12 <= slot_start.hour < 17

    if normalized == "soir":
        return slot_start.hour >= 17

    if "apres 17h" in normalized:
        return (
            slot_start.hour > 17
            or (
                slot_start.hour == 17
                and slot_start.minute >= 0
            )
        )

    if "avant 12h" in normalized:
        return slot_start.hour < 12

    return True


def _has_explicit_time_preference(
    preferred_time: str | None,
) -> bool:
    return bool(_normalize_match_text(preferred_time))


def build_recall_candidates(
    *,
    released_slot: dict,
    patients: list[dict],
    timezone_name: str | None = None,
    limit: int = 5,
) -> list[dict]:
    safe_limit = min(max(limit, 1), 20)

    cancelled_patient_id = released_slot.get(
        "cancelled_patient_id"
    )
    practitioner_name = _normalize_match_text(
        released_slot.get("practitioner_name")
    )
    slot_start = released_slot.get("start_at")
    local_slot_start = slot_start

    if (
        slot_start is not None
        and timezone_name
    ):
        local_slot_start = slot_start.astimezone(
            ZoneInfo(timezone_name)
        )

    french_weekdays = {
        0: "lundi",
        1: "mardi",
        2: "mercredi",
        3: "jeudi",
        4: "vendredi",
        5: "samedi",
        6: "dimanche",
    }

    slot_day = (
        french_weekdays.get(local_slot_start.weekday())
        if local_slot_start is not None
        else None
    )

    results: list[dict] = []

    for patient in patients:
        patient_id = patient.get("patient_id")

        if not patient.get("active", False):
            continue

        if patient_id == cancelled_patient_id:
            continue

        if patient.get("has_active_overlap", False):
            continue

        if patient.get(
            "has_active_future_appointment",
            False,
        ):
            continue

        preferences = patient.get("preferences") or {}
        score = 0
        reasons: list[str] = []

        preferred_practitioner = _normalize_match_text(
            preferences.get("preferred_practitioner")
        )

        if (
            practitioner_name
            and preferred_practitioner
            and preferred_practitioner != practitioner_name
        ):
            continue

        if (
            practitioner_name
            and preferred_practitioner
            and preferred_practitioner == practitioner_name
        ):
            score += 50
            reasons.append(
                "Praticien préféré correspondant"
            )

        preferred_day = _normalize_match_text(
            preferences.get("preferred_day")
        )

        if (
            slot_day
            and preferred_day
            and preferred_day != slot_day
        ):
            continue

        if (
            slot_day
            and preferred_day
            and preferred_day == slot_day
        ):
            score += 25
            reasons.append(
                "Jour préféré correspondant"
            )

        preferred_time = preferences.get("preferred_time")

        if (
            slot_start is not None
            and _has_explicit_time_preference(preferred_time)
            and not _preferred_time_matches(
                str(preferred_time),
                slot_start,
            )
        ):
            continue

        if (
            slot_start is not None
            and _has_explicit_time_preference(preferred_time)
            and _preferred_time_matches(
                str(preferred_time),
                slot_start,
            )
        ):
            score += 20
            reasons.append(
                "Horaire préféré correspondant"
            )

        last_goal = _normalize_match_text(
            patient.get("last_goal")
        )

        appointment_markers = (
            "rendez-vous",
            "rendez vous",
            "rdv",
        )

        has_appointment_goal = any(
            marker in last_goal
            for marker in appointment_markers
        )

        if has_appointment_goal:
            score += 15
            reasons.append(
                "Objectif récent lié à un rendez-vous"
            )

        if score >= 50:
            match_level = "primary"
        elif (
            has_appointment_goal
            and not patient.get(
                "has_active_future_appointment",
                False,
            )
        ):
            score += 15
            reasons.append(
                "Aucun rendez-vous actif futur"
            )
            match_level = "secondary"
        else:
            continue

        patient_name = patient.get("patient_name")

        french_weekdays_labels = {
            0: "lundi",
            1: "mardi",
            2: "mercredi",
            3: "jeudi",
            4: "vendredi",
            5: "samedi",
            6: "dimanche",
        }

        start_label = (
            f"{french_weekdays_labels[local_slot_start.weekday()]} "
            f"{_format_french_short_date(local_slot_start)} "
            f"à {local_slot_start.strftime('%H:%M')}"
        )

        draft_message = build_recall_message(
            patient_name=patient_name or "",
            practitioner_name=released_slot.get(
                "practitioner_name"
            ),
            start_label=start_label,
        )

        results.append(
            {
                "patient_id": patient_id,
                "patient_name": patient_name,
                "score": score,
                "match_level": match_level,
                "reasons": reasons,
                "requires_validation": True,
                "draft_message": draft_message,
            }
        )

    results.sort(
        key=lambda candidate: (
            -candidate["score"],
            _normalize_match_text(
                candidate.get("patient_name")
            ),
        )
    )

    return results[:safe_limit]





def build_recall_message(
    *,
    patient_name: str,
    practitioner_name: str | None,
    start_label: str,
) -> str:
    greeting = (
        f"Bonjour {patient_name},"
        if patient_name
        else "Bonjour,"
    )

    if practitioner_name:
        slot_sentence = (
            "Un créneau vient de se libérer avec "
            f"{practitioner_name} le {start_label}."
        )
    else:
        slot_sentence = (
            "Un créneau vient de se libérer "
            f"le {start_label}."
        )

    return (
        f"{greeting}\n\n"
        f"{slot_sentence}\n\n"
        "Souhaitez-vous en profiter ?\n\n"
        "Répondez simplement OUI pour que nous puissions "
        "vous le réserver."
    )



def _format_french_short_date(value: datetime) -> str:
    french_months = {
        1: "janvier",
        2: "février",
        3: "mars",
        4: "avril",
        5: "mai",
        6: "juin",
        7: "juillet",
        8: "août",
        9: "septembre",
        10: "octobre",
        11: "novembre",
        12: "décembre",
    }

    return f"{value.day} {french_months[value.month]}"


def _format_french_date(value: datetime) -> str:
    french_months = {
        1: "janvier",
        2: "février",
        3: "mars",
        4: "avril",
        5: "mai",
        6: "juin",
        7: "juillet",
        8: "août",
        9: "septembre",
        10: "octobre",
        11: "novembre",
        12: "décembre",
    }

    return (
        f"{value.day} "
        f"{french_months[value.month]} "
        f"{value.year}"
    )


def calculate_action_score(
    action_type: str,
    *,
    count: int = 1,
) -> int:
    if action_type == "cancelled":
        return min(100, 60 + max(0, count - 1) * 10)

    scores = {
        "no_show": 100,
        "late_active": 95,
        "recall_primary": 95,
        "pending_confirmation": 70,
        "recall_secondary": 65,
    }

    try:
        return scores[action_type]
    except KeyError as error:
        raise ValueError(
            f"Type d’action inconnu : {action_type}"
        ) from error


def build_recall_actions(
    *,
    released_slots: list[dict],
    timezone_name: str,
) -> list[dict]:
    timezone = ZoneInfo(timezone_name)
    actions: list[dict] = []

    for released_slot in released_slots:
        candidates = released_slot.get("recall_candidates") or []

        if not candidates:
            continue

        slot_start = released_slot.get("start_at")

        if slot_start is None:
            continue

        local_start = slot_start.astimezone(timezone)
        formatted_date = _format_french_date(local_start)
        formatted_time = local_start.strftime("%H:%M")

        primary_candidates = [
            candidate
            for candidate in candidates
            if candidate.get("match_level") == "primary"
        ]

        appointment_id = released_slot["appointment_id"]

        if primary_candidates:
            best_candidate = primary_candidates[0]
            patient_name = (
                best_candidate.get("patient_name")
                or "le patient sélectionné"
            )
            practitioner_name = (
                released_slot.get("practitioner_name")
                or "le praticien disponible"
            )

            actions.append(
                {
                    "id": f"propose_recall:{appointment_id}",
                    "priority": "high",
                    "score": calculate_action_score("recall_primary"),
                    "title": (
                        "1 patient prioritaire peut être rappelé"
                    ),
                    "description": (
                        "Un candidat fortement compatible a été "
                        "identifié pour le créneau libéré du "
                        f"{formatted_date} à {formatted_time}."
                    ),
                    "recommended_action": (
                        f"Vérifier le dossier de {patient_name} "
                        "et préparer une proposition de rendez-vous "
                        f"avec {practitioner_name}."
                    ),
                    "requires_validation": True,
                }
            )
            continue

        candidate_count = len(candidates)

        actions.append(
            {
                "id": f"propose_recall:{appointment_id}",
                "priority": "medium",
                "score": calculate_action_score("recall_secondary"),
                "title": (
                    f"{candidate_count} patient peut être rappelé"
                    if candidate_count == 1
                    else (
                        f"{candidate_count} patients peuvent être "
                        "rappelés"
                    )
                ),
                "description": (
                    "Un candidat secondaire a été identifié "
                    "pour le créneau libéré du "
                    f"{formatted_date} à {formatted_time}."
                    if candidate_count == 1
                    else (
                        "Des candidats secondaires ont été identifiés "
                        "pour le créneau libéré du "
                        f"{formatted_date} à {formatted_time}."
                    )
                ),
                "recommended_action": (
                    "Examiner les candidats et choisir le patient "
                    "à contacter avant de préparer une proposition."
                ),
                "requires_validation": True,
            }
        )

    return actions


def build_actions(
    *,
    priorities: dict,
) -> list[dict]:
    actions: list[dict] = []

    no_show = int(priorities.get("no_show", 0))
    late_active = int(priorities.get("late_active", 0))
    cancelled_today = int(priorities.get("cancelled_today", 0))
    pending_confirmation = int(
        priorities.get("pending_confirmation", 0)
    )

    if no_show > 0:
        actions.append(
            {
                "id": "review_no_show",
                "priority": "high",
                "score": calculate_action_score("no_show"),
                "title": (
                    f"{no_show} patient absent aujourd’hui"
                    if no_show == 1
                    else f"{no_show} patients absents aujourd’hui"
                ),
                "description": (
                    "Un rendez-vous est marqué comme non honoré."
                    if no_show == 1
                    else (
                        "Des rendez-vous sont marqués comme "
                        "non honorés."
                    )
                ),
                "recommended_action": (
                    "Vérifier le dossier et préparer une relance."
                ),
                "requires_validation": False,
            }
        )

    if late_active > 0:
        actions.append(
            {
                "id": "review_late_active",
                "priority": "high",
                "score": calculate_action_score("late_active"),
                "title": (
                    f"{late_active} rendez-vous actif est dépassé"
                    if late_active == 1
                    else (
                        f"{late_active} rendez-vous actifs "
                        "sont dépassés"
                    )
                ),
                "description": (
                    "Un rendez-vous encore actif a une heure "
                    "de début passée."
                    if late_active == 1
                    else (
                        "Des rendez-vous encore actifs ont une "
                        "heure de début passée."
                    )
                ),
                "recommended_action": (
                    "Vérifier son statut avant toute autre action."
                    if late_active == 1
                    else (
                        "Vérifier leurs statuts avant toute "
                        "autre action."
                    )
                ),
                "requires_validation": False,
            }
        )

    if cancelled_today > 0:
        actions.append(
            {
                "id": "review_cancelled",
                "priority": "high",
                "score": calculate_action_score(
                    "cancelled",
                    count=cancelled_today,
                ),
                "title": (
                    f"{cancelled_today} rendez-vous annulé aujourd’hui"
                    if cancelled_today == 1
                    else (
                        f"{cancelled_today} rendez-vous annulés "
                        "aujourd’hui"
                    )
                ),
                "description": (
                    "Cette annulation a potentiellement libéré "
                    "un créneau."
                    if cancelled_today == 1
                    else (
                        "Ces annulations ont potentiellement "
                        "libéré des créneaux."
                    )
                ),
                "recommended_action": (
                    "Examiner les créneaux et la liste des "
                    "patients à rappeler."
                ),
                "requires_validation": False,
            }
        )

    if pending_confirmation > 0:
        actions.append(
            {
                "id": "pending_confirmation",
                "priority": "medium",
                "score": calculate_action_score("pending_confirmation"),
                "title": (
                    f"{pending_confirmation} confirmation en attente"
                    if pending_confirmation == 1
                    else (
                        f"{pending_confirmation} confirmations "
                        "en attente"
                    )
                ),
                "description": (
                    "Un rendez-vous du jour est encore au "
                    "statut pending."
                    if pending_confirmation == 1
                    else (
                        "Des rendez-vous du jour sont encore au "
                        "statut pending."
                    )
                ),
                "recommended_action": (
                    "Préparer les confirmations patient."
                ),
                "requires_validation": False,
            }
        )

    return actions




async def answer_copilot_chat(
    *,
    cur,
    clinic_id,
    message: str,
) -> dict:
    cleaned_message = " ".join(message.strip().split())

    if not cleaned_message:
        return build_copilot_response(
            answer=(
                "Écrivez une question concernant la clinique."
            ),
            intent="unsupported",
            suggestions=[
                "Qui vient aujourd’hui ?",
                "Ouvre les patients",
            ],
        )

    tool_result = await execute_copilot_tool(
        cur=cur,
        clinic_id=clinic_id,
        message=cleaned_message,
    )

    if tool_result is not None:
        return tool_result

    return build_copilot_response(
        answer=(
            "Je peux rechercher un patient, consulter le "
            "planning, retrouver le prochain rendez-vous d’un "
            "patient ou d’un praticien, afficher les patients "
            "à recontacter, résumer les priorités du jour et "
            "ouvrir une page de DentalFlow. "
            "Exemples : « ouvre la fiche de Ahmed Benali », "
            "« qui vient aujourd’hui ? » ou "
            "« ouvre les paramètres »."
        ),
        intent="unsupported",
        suggestions=[
            "Ouvre la fiche de Ahmed Benali",
            "Qui vient aujourd’hui ?",
            "Ouvre les paramètres",
        ],
    )


async def create_recall_draft(
    *,
    cur,
    clinic_id,
    patient_id,
    appointment_id,
    message: str,
    candidate_score: int,
    match_level: str,
    reasons: list[str],
    created_by_user_id,
) -> dict:
    cleaned_message = message.strip()

    if not cleaned_message:
        raise ValueError(
            "Le brouillon ne peut pas être vide."
        )

    await cur.execute(
        """
        SELECT
            id,
            clinic_id,
            patient_id,
            appointment_id,
            channel,
            direction,
            event_type,
            external_id,
            payload,
            created_at
        FROM communication_events
        WHERE clinic_id = %s
          AND patient_id = %s
          AND appointment_id = %s
          AND channel = 'whatsapp'
          AND direction = 'outbound'
          AND event_type = 'recall_draft'
          AND payload->>'status' = 'draft'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (
            clinic_id,
            patient_id,
            appointment_id,
        ),
    )

    existing_draft = await cur.fetchone()

    if existing_draft is not None:
        return existing_draft

    payload = {
        "status": "draft",
        "message": cleaned_message,
        "candidate_score": candidate_score,
        "match_level": match_level,
        "reasons": reasons,
        "requires_validation": True,
        "created_by_user_id": str(created_by_user_id),
    }

    await cur.execute(
        """
        INSERT INTO communication_events (
            clinic_id,
            patient_id,
            appointment_id,
            channel,
            direction,
            event_type,
            external_id,
            payload
        )
        VALUES (
            %s,
            %s,
            %s,
            'whatsapp',
            'outbound',
            'recall_draft',
            NULL,
            %s
        )
        RETURNING
            id,
            clinic_id,
            patient_id,
            appointment_id,
            channel,
            direction,
            event_type,
            external_id,
            payload,
            created_at
        """,
        (
            clinic_id,
            patient_id,
            appointment_id,
            Jsonb(payload),
        ),
    )

    row = await cur.fetchone()

    if row is None:
        raise RuntimeError(
            "Le brouillon n’a pas pu être créé."
        )

    return row


async def build_daily_brief(
    *,
    cur,
    clinic_id: UUID,
    user: dict,
    now: datetime | None = None,
) -> dict:
    timezone_name = await clinic_timezone(cur, clinic_id)
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

    status_counts = {
        "pending": 0,
        "confirmed": 0,
        "cancelled": 0,
        "completed": 0,
        "no_show": 0,
    }

    for appointment in appointments:
        appointment_status = appointment.get("status")

        if appointment_status in status_counts:
            status_counts[appointment_status] += 1

    active_appointments = [
        appointment
        for appointment in appointments
        if appointment.get("status") in {"pending", "confirmed"}
    ]

    upcoming_appointments = [
        appointment
        for appointment in active_appointments
        if appointment.get("start_at") is not None
        and appointment["start_at"] >= local_now
    ]

    priorities = build_priorities(
        appointments=appointments,
        now=local_now,
    )
    released_slots = build_released_slots(
        appointments=appointments,
    )

    for released_slot in released_slots:
        patient_rows = await list_recall_candidate_patients(
            cur=cur,
            clinic_id=clinic_id,
            cancelled_patient_id=released_slot[
                "cancelled_patient_id"
            ],
            slot_start=released_slot["start_at"],
            slot_end=released_slot["end_at"],
            limit=100,
        )

        released_slot["recall_candidates"] = (
            build_recall_candidates(
                released_slot=released_slot,
                patients=patient_rows,
                timezone_name=timezone_name,
                limit=5,
            )
        )

    raw_overdue_recall_patients = await list_overdue_recall_patients(
        cur=cur,
        clinic_id=clinic_id,
        now=local_now,
        minimum_months=12,
        limit=20,
    )

    actions = build_actions(
        priorities=priorities,
    )
    actions.extend(
        build_recall_actions(
            released_slots=released_slots,
            timezone_name=timezone_name,
        )
    )

    actions.sort(
        key=lambda action: action["score"],
        reverse=True,
    )

    return {
        "date": local_now.date().isoformat(),
        "timezone": timezone_name,
        "clinic_id": str(clinic_id),
        "user": {
            "id": str(user["id"]),
            "full_name": user.get("full_name"),
            "role": user.get("role"),
        },
        "summary": {
            "total": len(appointments),
            **status_counts,
            "active": len(active_appointments),
            "upcoming": len(upcoming_appointments),
        },
        "priorities": priorities,
        "actions": actions,
        "released_slots": released_slots,
        "overdue_recall_patients": enrich_overdue_recall_patients(
            patients=raw_overdue_recall_patients,
            now=local_now,
        ),
        "appointments": appointments,
    }
