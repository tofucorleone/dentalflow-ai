from __future__ import annotations

import re
from uuid import UUID

from app.conversations.repository import (
    get_conversation_thread,
    list_conversation_messages,
)


INTENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("urgence_dentaire", ("urgence", "urgent", "douleur", "mal", "gonfl", "saigne", "cassé", "cassee", "abcès", "abces")),
    ("prise_rendez_vous", ("rendez-vous", "rendez vous", "rdv", "disponible", "créneau", "creneau", "réserver", "reserver")),
    ("deplacement_rendez_vous", ("déplacer", "deplacer", "reporter", "changer l'heure", "changer la date")),
    ("annulation_rendez_vous", ("annuler", "annulation", "ne pourrai pas venir", "ne peux pas venir")),
    ("tarif_soin", ("prix", "tarif", "combien", "coût", "cout", "devis")),
    ("document", ("ordonnance", "radio", "radiographie", "document", "facture", "certificat")),
)


def _normalized_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower().strip())


def _detect_intents(messages: list[dict]) -> list[str]:
    recent_patient_text = " ".join(
        _normalized_text(message.get("body"))
        for message in messages[-20:]
        if message.get("direction") == "inbound"
    )
    intents = [intent for intent, keywords in INTENT_RULES if any(keyword in recent_patient_text for keyword in keywords)]
    if not intents and recent_patient_text:
        intents.append("demande_generale")
    return intents


def _priority(*, intents: list[str], unread_count: int, control_mode: str) -> tuple[str, int, list[str]]:
    reasons: list[str] = []
    score = 20
    if "urgence_dentaire" in intents:
        score += 65
        reasons.append("Des termes associés à une urgence ou à une douleur ont été détectés.")
    if unread_count >= 3:
        score += 20
        reasons.append(f"La conversation contient {unread_count} messages non lus.")
    elif unread_count > 0:
        score += 10
        reasons.append("La conversation contient un message non lu.")
    if "prise_rendez_vous" in intents:
        score += 10
        reasons.append("Le patient semble demander un rendez-vous.")
    if control_mode == "human_active":
        score += 5
        reasons.append("La conversation est actuellement sous contrôle humain.")
    score = min(score, 100)
    if score >= 70:
        return "high", score, reasons
    if score >= 40:
        return "medium", score, reasons
    return "low", score, reasons


def _summary(thread: dict, messages: list[dict], intents: list[str]) -> str:
    patient_messages = [m for m in messages if m.get("direction") == "inbound" and _normalized_text(m.get("body"))]
    if not patient_messages:
        return "Aucun message patient exploitable n’est encore disponible dans cette conversation."
    latest = str(patient_messages[-1].get("body") or "").strip()
    if len(latest) > 180:
        latest = latest[:177].rstrip() + "…"
    if intents:
        intent_text = ", ".join(intent.replace("_", " ") for intent in intents[:3])
        return f"Dernière demande : « {latest} ». Intentions probables : {intent_text}."
    return f"Dernière demande du patient : « {latest} »."


def _recommended_actions(*, thread: dict, intents: list[str], priority: str) -> list[dict]:
    actions: list[dict] = []
    if priority == "high":
        actions.append({"type": "review_urgent", "label": "Évaluer rapidement", "description": "Faire relire la conversation par un membre de l’équipe avant toute réponse automatique.", "requires_validation": True})
    if "prise_rendez_vous" in intents or "urgence_dentaire" in intents:
        actions.append({"type": "prepare_appointment", "label": "Préparer un rendez-vous", "description": "Rechercher des créneaux adaptés, sans créer de rendez-vous automatiquement.", "requires_validation": True})
    if "deplacement_rendez_vous" in intents:
        actions.append({"type": "prepare_reschedule", "label": "Préparer un déplacement", "description": "Identifier le rendez-vous concerné et proposer des alternatives.", "requires_validation": True})
    if "annulation_rendez_vous" in intents:
        actions.append({"type": "prepare_cancellation", "label": "Vérifier l’annulation", "description": "Identifier le rendez-vous avant de préparer son annulation.", "requires_validation": True})
    if thread.get("patient_id") is None:
        actions.append({"type": "link_patient", "label": "Rattacher le contact", "description": "Rechercher ou créer la fiche patient correspondant à ce numéro.", "requires_validation": True})
    if not actions:
        actions.append({"type": "review_conversation", "label": "Relire la conversation", "description": "Vérifier le contexte avant de répondre au patient.", "requires_validation": False})
    return actions[:4]


async def _patient_context(*, cur, clinic_id: UUID, thread: dict) -> dict:
    patient_id = thread.get("patient_id")
    if patient_id is None:
        return {"identified": False, "full_name": None, "phone": thread.get("sender_phone"), "ai_summary": None, "last_goal": None, "preferences": {}, "recent_notes": [], "medical_history": [], "next_appointment": None, "last_completed_appointment": None}

    await cur.execute(
        """
        SELECT p.full_name, p.phone, m.summary AS ai_summary,
               m.last_goal, COALESCE(m.preferences, '{}'::jsonb) AS preferences
        FROM patients p
        LEFT JOIN patient_ai_memory m
          ON m.patient_id = p.id AND m.clinic_id = p.clinic_id
        WHERE p.id = %s AND p.clinic_id = %s
        LIMIT 1
        """,
        (patient_id, clinic_id),
    )
    patient = await cur.fetchone()
    if patient is None:
        return {"identified": False, "full_name": thread.get("patient_name"), "phone": thread.get("sender_phone"), "ai_summary": None, "last_goal": None, "preferences": {}, "recent_notes": [], "medical_history": [], "next_appointment": None, "last_completed_appointment": None}

    await cur.execute(
        """
        SELECT author_name, note
        FROM patient_notes
        WHERE patient_id = %s AND clinic_id = %s
        ORDER BY created_at DESC
        LIMIT 3
        """,
        (patient_id, clinic_id),
    )
    notes = await cur.fetchall()

    await cur.execute(
        """
        SELECT category, value
        FROM medical_history
        WHERE patient_id = %s AND clinic_id = %s AND is_active = TRUE
        ORDER BY created_at DESC
        LIMIT 5
        """,
        (patient_id, clinic_id),
    )
    history = await cur.fetchall()

    appointment_select = """
        SELECT a.id, a.status, a.start_at, a.end_at,
               pr.full_name AS practitioner_name,
               t.name AS treatment_name
        FROM appointments a
        LEFT JOIN practitioners pr
          ON pr.id = a.practitioner_id AND pr.clinic_id = a.clinic_id
        LEFT JOIN treatments t
          ON t.id = a.treatment_id AND t.clinic_id = a.clinic_id
        WHERE a.clinic_id = %s AND a.patient_id = %s
    """
    await cur.execute(appointment_select + " AND a.status IN ('pending', 'confirmed') AND a.start_at >= NOW() ORDER BY a.start_at ASC LIMIT 1", (clinic_id, patient_id))
    next_appointment = await cur.fetchone()
    await cur.execute(appointment_select + " AND a.status = 'completed' ORDER BY a.start_at DESC LIMIT 1", (clinic_id, patient_id))
    last_completed = await cur.fetchone()

    return {
        "identified": True,
        "full_name": patient.get("full_name"),
        "phone": patient.get("phone") or thread.get("sender_phone"),
        "ai_summary": patient.get("ai_summary"),
        "last_goal": patient.get("last_goal"),
        "preferences": patient.get("preferences") if isinstance(patient.get("preferences"), dict) else {},
        "recent_notes": [f"{row.get('author_name') or 'Équipe clinique'} : {row.get('note')}" for row in notes if row.get("note")],
        "medical_history": [f"{row.get('category')} : {row.get('value')}" for row in history if row.get("value")],
        "next_appointment": next_appointment,
        "last_completed_appointment": last_completed,
    }


async def _patient_timeline(
    *,
    cur,
    clinic_id: UUID,
    thread: dict,
    messages: list[dict],
) -> list[dict]:
    events: list[dict] = []

    for message in messages[-8:]:
        body = str(message.get("body") or "").strip()
        occurred_at = message.get("occurred_at")

        if not body or occurred_at is None:
            continue

        direction = str(message.get("direction") or "inbound")
        author_type = str(message.get("author_type") or "patient")
        title = (
            "Message du patient"
            if direction == "inbound"
            else "Réponse de l’équipe"
        )

        if author_type == "ai":
            title = "Réponse IA"
        elif author_type == "system":
            title = "Message WhatsApp de la clinique"

        events.append(
            {
                "id": f"message:{message['id']}",
                "type": "conversation",
                "occurred_at": occurred_at,
                "title": title,
                "description": (
                    body[:157].rstrip() + "…"
                    if len(body) > 160
                    else body
                ),
                "status": message.get("status"),
                "direction": direction,
            }
        )

    patient_id = thread.get("patient_id")

    if patient_id is not None:
        await cur.execute(
            """
            SELECT
                a.id,
                a.status,
                a.start_at,
                pr.full_name AS practitioner_name,
                t.name AS treatment_name
            FROM appointments a
            LEFT JOIN practitioners pr
              ON pr.id = a.practitioner_id
             AND pr.clinic_id = a.clinic_id
            LEFT JOIN treatments t
              ON t.id = a.treatment_id
             AND t.clinic_id = a.clinic_id
            WHERE a.clinic_id = %s
              AND a.patient_id = %s
            ORDER BY a.start_at DESC
            LIMIT 8
            """,
            (clinic_id, patient_id),
        )

        for appointment in await cur.fetchall():
            details = [
                appointment.get("treatment_name"),
                appointment.get("practitioner_name"),
            ]
            events.append(
                {
                    "id": f"appointment:{appointment['id']}",
                    "type": "appointment",
                    "occurred_at": appointment["start_at"],
                    "title": "Rendez-vous patient",
                    "description": " · ".join(
                        str(value) for value in details if value
                    ) or None,
                    "status": appointment.get("status"),
                    "direction": None,
                }
            )

        await cur.execute(
            """
            SELECT
                id,
                author_name,
                note,
                created_at
            FROM patient_notes
            WHERE clinic_id = %s
              AND patient_id = %s
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (clinic_id, patient_id),
        )

        for note in await cur.fetchall():
            note_text = str(note.get("note") or "").strip()

            if not note_text:
                continue

            events.append(
                {
                    "id": f"note:{note['id']}",
                    "type": "note",
                    "occurred_at": note["created_at"],
                    "title": "Note clinique",
                    "description": (
                        f"{note.get('author_name') or 'Équipe clinique'} : "
                        f"{note_text[:180]}"
                    ),
                    "status": None,
                    "direction": None,
                }
            )

    events.sort(
        key=lambda event: event["occurred_at"],
        reverse=True,
    )

    return events[:14]


async def build_conversation_insight(*, cur, clinic_id: UUID, thread_id: UUID) -> dict | None:
    thread = await get_conversation_thread(cur=cur, clinic_id=clinic_id, thread_id=thread_id)
    if thread is None:
        return None
    messages = await list_conversation_messages(cur=cur, clinic_id=clinic_id, thread_id=thread_id, limit=100, offset=0)
    intents = _detect_intents(messages)
    priority, score, reasons = _priority(intents=intents, unread_count=int(thread.get("unread_count") or 0), control_mode=str(thread.get("control_mode") or "ai_active"))
    patient_context = await _patient_context(cur=cur, clinic_id=clinic_id, thread=thread)
    patient_timeline = await _patient_timeline(
        cur=cur,
        clinic_id=clinic_id,
        thread=thread,
        messages=messages,
    )
    return {
        "thread_id": thread["id"], "patient_id": thread.get("patient_id"), "patient_name": thread.get("patient_name"),
        "sender_phone": thread["sender_phone"], "summary": _summary(thread, messages, intents),
        "priority": priority, "priority_score": score, "priority_reasons": reasons, "intents": intents,
        "recommended_actions": _recommended_actions(thread=thread, intents=intents, priority=priority),
        "message_count": len(messages), "control_mode": thread.get("control_mode") or "ai_active",
        "last_message_at": thread.get("last_message_at"), "patient_context": patient_context,
        "patient_timeline": patient_timeline, "read_only": True,
    }


__all__ = ["build_conversation_insight"]
