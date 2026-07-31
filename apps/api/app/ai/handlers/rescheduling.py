from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from app.ai.confirmation_parser import parse_confirmation
from app.ai.conversation_state import save_conversation_state
from app.ai.message_parser import extract_message_parts
from app.ai.conversation_reference_resolver import (
    resolve_relative_reference,
)
from app.ai.schemas import ConversationChannel, ConversationResult
from app.ai.slot_selection import extract_selected_slot_index
from app.appointment_service import get_next_patient_appointment


async def handle_rescheduling(
    clinic_id: UUID,
    channel: ConversationChannel,
    patient: dict | None,
    message: str,
) -> ConversationResult:
    if patient is None:
        return ConversationResult(
            intent="reschedule_appointment",
            requires_human=True,
            reply=(
                "Je peux vous aider à déplacer un rendez-vous. "
                "Pouvez-vous me communiquer votre nom complet ?"
            ),
        )

    appointment = await get_next_patient_appointment(
        clinic_id=clinic_id,
        patient_id=patient["id"],
    )

    if appointment is None:
        return ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient["id"],
            reply="Je n'ai trouvé aucun rendez-vous à venir à déplacer.",
        )

    local_start = appointment["start_at"].astimezone(
        ZoneInfo("Africa/Algiers"),
    )

    parts = extract_message_parts(message)

    base_context = {
        "intent": "reschedule_appointment",
        "appointment_id": str(appointment["id"]),
        "previous_start_at": appointment["start_at"].isoformat(),
        "previous_end_at": appointment["end_at"].isoformat(),
        "practitioner_id": (
            str(appointment["practitioner_id"])
            if appointment["practitioner_id"]
            else None
        ),
        "practitioner_name": appointment["practitioner_name"],
        "treatment_id": (
            str(appointment["treatment_id"])
            if appointment["treatment_id"]
            else None
        ),
        "treatment_name": appointment["treatment_name"],
    }

    if parts.date_text is not None:
        date_context = {
            **base_context,
            "requested_date_text": parts.date_text,
        }

        if parts.time_text is not None:
            await save_conversation_state(
                clinic_id=clinic_id,
                patient_id=patient["id"],
                channel=channel,
                state="waiting_for_reschedule_time",
                context=date_context,
            )

            return await handle_rescheduling_time_response(
                clinic_id=clinic_id,
                channel=channel,
                patient=patient,
                message=parts.time_text,
                current_context=date_context,
            )

        return await handle_rescheduling_date_response(
            clinic_id=clinic_id,
            channel=channel,
            patient=patient,
            message=parts.date_text,
            current_context=base_context,
        )

    await save_conversation_state(
        clinic_id=clinic_id,
        patient_id=patient["id"],
        channel=channel,
        state="waiting_for_reschedule_date",
        context=base_context,
    )

    return ConversationResult(
        intent="reschedule_appointment",
        patient_id=patient["id"],
        reply=(
            "Votre prochain rendez-vous est prévu le "
            f"{local_start.strftime('%d/%m/%Y à %Hh%M')}. "
            "À quelle nouvelle date souhaitez-vous le déplacer ?"
        ),
    )


async def handle_rescheduling_date_response(
    clinic_id: UUID,
    channel: ConversationChannel,
    patient: dict,
    message: str,
    current_context: dict | None = None,
) -> ConversationResult:
    message = resolve_relative_reference(
        message=message,
        context=current_context,
    )

    parts = extract_message_parts(message)
    requested_date = parts.date_text or message.strip()
    context = dict(current_context or {})

    if not context.get("appointment_id"):
        return ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient["id"],
            reply=(
                "Je n'ai pas retrouvé le rendez-vous à déplacer. "
                "Pouvez-vous recommencer votre demande ?"
            ),
            requires_human=True,
        )

    context.update(
        {
            "intent": "reschedule_appointment",
            "requested_date_text": requested_date,
        }
    )

    if parts.time_text is not None:
        return await handle_rescheduling_time_response(
            clinic_id=clinic_id,
            channel=channel,
            patient=patient,
            message=parts.time_text,
            current_context=context,
        )

    await save_conversation_state(
        clinic_id=clinic_id,
        patient_id=patient["id"],
        channel=channel,
        state="waiting_for_reschedule_time",
        context=context,
    )

    return ConversationResult(
        intent="reschedule_appointment",
        patient_id=patient["id"],
        reply=(
            f"Très bien, vous souhaitez déplacer le rendez-vous à {requested_date}. "
            "À quelle heure souhaitez-vous venir ?"
        ),
    )


async def handle_rescheduling_time_response(
    clinic_id: UUID,
    channel: ConversationChannel,
    patient: dict,
    message: str,
    current_context: dict | None = None,
) -> ConversationResult:
    from fastapi import HTTPException

    from app.ai.booking_availability import (
        check_booking_availability,
        find_available_slots_for_preference,
    )
    from app.ai.booking_datetime import (
        BookingDateTimeError,
        normalize_text,
    )
    from app.ai.time_preferences import (
        TimePreferenceError,
        format_time_preference_label,
        parse_time_preference,
    )

    message = resolve_relative_reference(
        message=message,
        context=current_context,
    )

    parts = extract_message_parts(message)
    context = dict(current_context or {})

    if parts.date_text is not None:
        context["requested_date_text"] = parts.date_text

    requested_time = (
        parts.time_text
        if parts.time_text is not None
        else message.strip()
    )

    appointment_id = context.get("appointment_id")
    requested_date = context.get("requested_date_text")

    practitioner_id_text = context.get("practitioner_id")
    practitioner_id = (
        UUID(practitioner_id_text)
        if practitioner_id_text
        else None
    )

    treatment_id_text = context.get("treatment_id")
    treatment_id = (
        UUID(treatment_id_text)
        if treatment_id_text
        else None
    )

    if not appointment_id or not requested_date:
        return ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient["id"],
            reply=(
                "Je n'ai pas retrouvé toutes les informations "
                "du rendez-vous à déplacer. "
                "Pouvez-vous recommencer votre demande ?"
            ),
            requires_human=True,
        )

    selected_slot_index = extract_selected_slot_index(message)

    if selected_slot_index is not None:
        suggested_slots = context.get("suggested_slots", [])

        if selected_slot_index == -1:
            slot_position = len(suggested_slots) - 1
        else:
            slot_position = selected_slot_index - 1

        if 0 <= slot_position < len(suggested_slots):
            selected_slot = suggested_slots[slot_position]
            selected_start = datetime.fromisoformat(
                selected_slot["start_at"],
            )

            requested_time = selected_start.strftime("%Hh%M")
            practitioner_id = UUID(
                selected_slot["practitioner_id"],
            )

    try:
        preference = parse_time_preference(requested_time)
    except TimePreferenceError:
        preference = None

    if preference is not None and preference.exact_time is None:
        try:
            suggestions = await find_available_slots_for_preference(
                clinic_id=clinic_id,
                date_text=requested_date,
                preference=preference,
                practitioner_id=practitioner_id,
                treatment_id=treatment_id,
                exclude_appointment_id=UUID(appointment_id),
                limit=3,
            )
        except BookingDateTimeError as exc:
            return ConversationResult(
                intent="reschedule_appointment",
                patient_id=patient["id"],
                reply=str(exc),
            )

        if not suggestions:
            return ConversationResult(
                intent="reschedule_appointment",
                patient_id=patient["id"],
                reply=(
                    "Je n'ai trouvé aucun créneau disponible "
                    f"{requested_time} pour {requested_date}. "
                    "Pouvez-vous choisir une autre préférence horaire ?"
                ),
            )

        suggestion_lines = [
            f"• {start_at.strftime('%Hh%M')}"
            for _, start_at, _ in suggestions
        ]

        suggested_slots = [
            {
                "practitioner_id": str(
                    suggested_practitioner_id
                ),
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
            }
            for suggested_practitioner_id, start_at, end_at
            in suggestions
        ]

        context["suggested_slots"] = suggested_slots

        automatic_first_slot_preferences = {
            "le plus tot possible",
            "plus tot possible",
            "premier creneau",
            "premier creneau disponible",
            "n'importe quand",
            "quand vous voulez",
        }

        if (
            normalize_text(requested_time)
            in automatic_first_slot_preferences
        ):
            first_start_at = suggestions[0][1]

            return await handle_rescheduling_time_response(
                clinic_id=clinic_id,
                channel=channel,
                patient=patient,
                message=first_start_at.strftime("%Hh%M"),
                current_context=context,
            )

        await save_conversation_state(
            clinic_id=clinic_id,
            patient_id=patient["id"],
            channel=channel,
            state="waiting_for_reschedule_time",
            context=context,
        )

        return ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient["id"],
            reply=(
                "Voici les premiers créneaux disponibles "
                f"{format_time_preference_label(requested_date, requested_time)} "
                ":\n\n"
                + "\n".join(suggestion_lines)
                + "\n\nQuel créneau préférez-vous ?"
            ),
            metadata={
                "suggested_slots": suggested_slots,
            },
        )

    if preference is not None and preference.exact_time is not None:
        for suggested_slot in context.get("suggested_slots", []):
            suggested_start = datetime.fromisoformat(
                suggested_slot["start_at"]
            )

            if (
                suggested_start.hour == preference.exact_time.hour
                and suggested_start.minute == preference.exact_time.minute
            ):
                practitioner_id = UUID(
                    suggested_slot["practitioner_id"]
                )
                break

    try:
        _, start_at, end_at = await check_booking_availability(
            clinic_id=clinic_id,
            date_text=requested_date,
            time_text=requested_time,
            practitioner_id=practitioner_id,
            treatment_id=treatment_id,
            exclude_appointment_id=UUID(appointment_id),
        )
    except BookingDateTimeError as exc:
        return ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient["id"],
            reply=str(exc),
        )
    except HTTPException as exc:
        detail = exc.detail

        if isinstance(detail, dict):
            error_message = detail.get(
                "message",
                "Ce créneau n'est pas disponible.",
            )
        else:
            error_message = str(detail)

        return ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient["id"],
            reply=(
                f"{error_message} "
                "Pouvez-vous choisir une autre heure ?"
            ),
        )

    context.pop("suggested_slots", None)

    context.update(
        {
            "intent": "reschedule_appointment",
            "requested_time_text": requested_time,
            "practitioner_id": str(practitioner_id),
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
        }
    )

    await save_conversation_state(
        clinic_id=clinic_id,
        patient_id=patient["id"],
        channel=channel,
        state="waiting_for_confirmation",
        context=context,
    )

    practitioner_name = context.get("practitioner_name")
    treatment_name = context.get("treatment_name")

    details = []

    if practitioner_name:
        if practitioner_name.lower().startswith("dr "):
            details.append(f"avec le {practitioner_name}")
        else:
            details.append(f"avec {practitioner_name}")

    if treatment_name:
        details.append(
            f"pour votre {treatment_name.lower()}"
        )

    details_text = (
        " " + " ".join(details)
        if details
        else ""
    )

    return ConversationResult(
        intent="reschedule_appointment",
        patient_id=patient["id"],
        reply=(
            f"Le nouveau créneau {requested_date} à {requested_time}"
            f"{details_text} est disponible. "
            "Confirmez-vous le déplacement ?"
        ),
    )


async def handle_rescheduling_confirmation(
    clinic_id: UUID,
    channel: ConversationChannel,
    patient: dict,
    message: str,
    current_context: dict | None = None,
) -> ConversationResult:
    from datetime import datetime

    from fastapi import HTTPException

    from app.appointment_service import reschedule_appointment_record
    from app.db import connection
    from app.schemas import AppointmentRescheduleIn

    confirmation = parse_confirmation(message)
    normalized_answer = " ".join(message.strip().lower().split())
    context = dict(current_context or {})

    appointment_id = context.get("appointment_id")
    start_at = context.get("start_at")
    end_at = context.get("end_at")

    if confirmation is False or normalized_answer in {
        "annuler",
        "garder",
    }:
        await save_conversation_state(
            clinic_id=clinic_id,
            patient_id=patient["id"],
            channel=channel,
            state="completed",
            context={
                **context,
                "rescheduled": False,
            },
        )

        return ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient["id"],
            reply="Très bien, votre rendez-vous reste inchangé.",
        )

    if confirmation is None and normalized_answer not in {
        "annuler",
        "garder",
    }:
        return ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient["id"],
            reply=(
                "Pouvez-vous répondre par « oui » pour confirmer "
                "ou « non » pour conserver l'ancien créneau ?"
            ),
        )

    if not appointment_id or not start_at or not end_at:
        return ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient["id"],
            reply=(
                "Je n'ai pas retrouvé toutes les informations "
                "nécessaires au déplacement. "
                "Pouvez-vous recommencer votre demande ?"
            ),
            requires_human=True,
        )

    payload = AppointmentRescheduleIn(
        start_at=datetime.fromisoformat(start_at),
        end_at=datetime.fromisoformat(end_at),
    )

    try:
        async with connection() as conn:
            async with conn.cursor() as cur:
                appointment = await reschedule_appointment_record(
                    cur=cur,
                    conn=conn,
                    clinic_id=clinic_id,
                    appointment_id=UUID(appointment_id),
                    payload=payload,
                )
    except HTTPException as exc:
        detail = exc.detail

        if isinstance(detail, dict):
            error_message = detail.get(
                "message",
                "Impossible de déplacer ce rendez-vous.",
            )
        else:
            error_message = str(detail)

        return ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient["id"],
            reply=(
                f"{error_message} "
                "Souhaitez-vous essayer un autre créneau ?"
            ),
            requires_human=exc.status_code >= 500,
        )

    await save_conversation_state(
        clinic_id=clinic_id,
        patient_id=patient["id"],
        channel=channel,
        state="completed",
        context={
            **context,
            "rescheduled": True,
        },
    )

    requested_date = context.get(
        "requested_date_text",
        "la date choisie",
    )
    requested_time = context.get(
        "requested_time_text",
        "l'heure choisie",
    )

    return ConversationResult(
        intent="reschedule_appointment",
        patient_id=patient["id"],
        reply=(
            f"Votre rendez-vous a bien été déplacé à "
            f"{requested_date} à {requested_time} ✅"
        ),
        metadata={
            "appointment_id": appointment_id,
            "start_at": appointment["start_at"].isoformat(),
            "end_at": appointment["end_at"].isoformat(),
            "rescheduled": True,
        },
    )
