from html import escape
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import Response

from app.ai.processor import process_conversation
from app.ai.schemas import ConversationInput
from app.config import get_settings
from app.db import connection
from app.voice.twilio_security import (
    require_valid_twilio_signature,
)


router = APIRouter(
    prefix="/whatsapp",
    tags=["Assistant WhatsApp - Twilio"],
)


def _normalize_twilio_whatsapp_address(
    value: str,
) -> str:
    cleaned = value.strip()

    prefix = "whatsapp:"

    if cleaned.lower().startswith(prefix):
        cleaned = cleaned[len(prefix):]

    return cleaned.strip()


def _build_messaging_twiml(
    message: str,
) -> str:
    safe_message = escape(
        message.strip(),
        quote=False,
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{safe_message}</Message>
</Response>"""


async def _get_sandbox_clinic() -> dict | None:
    settings = get_settings()
    configured_id = (
        settings.twilio_whatsapp_sandbox_clinic_id
        or ""
    ).strip()

    if not configured_id:
        return None

    try:
        clinic_id = UUID(configured_id)
    except ValueError:
        return None

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    name,
                    display_name,
                    phone,
                    whatsapp_number,
                    timezone,
                    language
                FROM clinics
                WHERE id = %s
                  AND active = TRUE
                LIMIT 1
                """,
                (clinic_id,),
            )

            return await cur.fetchone()


@router.post(
    "/twilio",
    response_class=Response,
)
async def twilio_whatsapp_message(
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str | None = Form(default=None),
    ProfileName: str | None = Form(default=None),
    NumMedia: str | None = Form(default=None),
    _: None = Depends(
        require_valid_twilio_signature,
    ),
) -> Response:
    """
    Reçoit un message WhatsApp depuis le Sandbox Twilio
    et le transmet au moteur conversationnel DentalFlow.
    """

    sender_phone = _normalize_twilio_whatsapp_address(
        From,
    )
    called_number = _normalize_twilio_whatsapp_address(
        To,
    )
    message = Body.strip()

    if not sender_phone or not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message WhatsApp invalide.",
        )

    clinic = await _get_sandbox_clinic()

    if clinic is None:
        twiml = _build_messaging_twiml(
            "Le service WhatsApp du cabinet "
            "n'est pas encore configuré."
        )

        return Response(
            content=twiml,
            media_type="application/xml",
        )

    conversation = ConversationInput(
        clinic_id=clinic["id"],
        channel="whatsapp",
        sender_phone=sender_phone,
        message=message,
        external_id=MessageSid,
        session_id=None,
        metadata={
            "provider": "twilio",
            "input_source": "twilio_whatsapp",
            "called_number": called_number,
            "profile_name": ProfileName,
            "num_media": NumMedia,
        },
    )

    result = await process_conversation(
        conversation,
    )

    twiml = _build_messaging_twiml(
        result.reply,
    )

    return Response(
        content=twiml,
        media_type="application/xml",
        headers={
            "X-DentalFlow-Channel": "whatsapp",
            "X-DentalFlow-Intent": result.intent,
            "X-DentalFlow-Requires-Human": (
                "true"
                if result.requires_human
                else "false"
            ),
        },
    )


__all__ = [
    "router",
]
