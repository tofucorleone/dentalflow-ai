from uuid import UUID
from zoneinfo import ZoneInfo

from app.ai.confirmation_parser import parse_confirmation
from app.ai.conversation_state import save_conversation_state
from app.ai.schemas import ConversationChannel, ConversationResult
from app.appointment_service import get_next_patient_appointment


async def handle_cancellation(
    clinic_id: UUID,
    channel: ConversationChannel,
    patient: dict | None,
) -> ConversationResult:
    if patient is None:
        return ConversationResult(
            intent="cancel_appointment",
            requires_human=True,
            reply=(
                "Je peux vous aider à annuler un rendez-vous. "
                "Pouvez-vous me communiquer votre nom complet ?"
            ),
        )

    appointment = await get_next_patient_appointment(
        clinic_id=clinic_id,
        patient_id=patient["id"],
    )

    if appointment is None:
        return ConversationResult(
            intent="cancel_appointment",
            patient_id=patient["id"],
            reply="Je n'ai trouvé aucun rendez-vous à venir à annuler.",
        )

    local_start = appointment["start_at"].astimezone(
        ZoneInfo("Africa/Algiers"),
    )

    await save_conversation_state(
        clinic_id=clinic_id,
        patient_id=patient["id"],
        channel=channel,
        state="waiting_for_confirmation",
        context={
            "intent": "cancel_appointment",
            "appointment_id": str(appointment["id"]),
        },
    )

    return ConversationResult(
        intent="cancel_appointment",
        patient_id=patient["id"],
        reply=(
            "Souhaitez-vous annuler votre rendez-vous du "
            f"{local_start.strftime('%d/%m/%Y à %Hh%M')} ? "
            "Répondez par « oui » ou « non »."
        ),
    )


async def handle_cancellation_confirmation(
    clinic_id: UUID,
    channel: ConversationChannel,
    patient: dict,
    message: str,
    current_context: dict | None = None,
) -> ConversationResult:
    from fastapi import HTTPException

    from app.appointment_service import cancel_appointment_record
    from app.db import connection

    confirmation = parse_confirmation(message)
    normalize_answer = " ".join(message.strip().lower().split())
    context = dict(current_context or {})
    appointment_id = context.get("appointment_id")

    if not appointment_id:
        return ConversationResult(
            intent="cancel_appointment",
            patient_id=patient["id"],
            reply=(
                "Je n'ai pas retrouvé le rendez-vous à annuler. "
                "Pouvez-vous recommencer votre demande ?"
            ),
            requires_human=True,
        )

    if confirmation is False or normalize_answer in {"garder", "conserver"}:
        await save_conversation_state(
            clinic_id=clinic_id,
            patient_id=patient["id"],
            channel=channel,
            state="completed",
            context={
                **context,
                "cancelled": False,
            },
        )

        return ConversationResult(
            intent="cancel_appointment",
            patient_id=patient["id"],
            reply="Très bien, votre rendez-vous est conservé.",
        )

    if confirmation is None and normalize_answer not in {
        "garder",
        "conserver",
    }:
        return ConversationResult(
            intent="cancel_appointment",
            patient_id=patient["id"],
            reply=(
                "Pouvez-vous répondre par « oui » pour annuler "
                "ou « non » pour conserver le rendez-vous ?"
            ),
        )

    try:
        async with connection() as conn:
            async with conn.cursor() as cur:
                result = await cancel_appointment_record(
                    cur=cur,
                    conn=conn,
                    clinic_id=clinic_id,
                    appointment_id=UUID(appointment_id),
                )
    except HTTPException as exc:
        detail = exc.detail

        if isinstance(detail, dict):
            error_message = detail.get(
                "message",
                "Impossible d'annuler ce rendez-vous.",
            )
        else:
            error_message = str(detail)

        return ConversationResult(
            intent="cancel_appointment",
            patient_id=patient["id"],
            reply=error_message,
            requires_human=exc.status_code >= 500,
        )

    await save_conversation_state(
        clinic_id=clinic_id,
        patient_id=patient["id"],
        channel=channel,
        state="completed",
        context={
            **context,
            "cancelled": True,
        },
    )

    already_cancelled = result.get("already_cancelled", False)

    return ConversationResult(
        intent="cancel_appointment",
        patient_id=patient["id"],
        reply=(
            "Ce rendez-vous était déjà annulé."
            if already_cancelled
            else "Votre rendez-vous a bien été annulé."
        ),
        metadata={
            "appointment_id": appointment_id,
            "cancelled": True,
        },
    )
