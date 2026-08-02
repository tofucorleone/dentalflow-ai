from html import escape

from fastapi import APIRouter, Form
from fastapi.responses import Response

from app.ai.processor import process_conversation
from app.ai.schemas import ConversationInput
from app.voice.clinic_resolver import (
    find_active_clinic_by_voice_number,
)
from app.voice.transcription import (
    VoiceTranscriptionError,
    transcribe_audio,
)
from app.voice.twilio_media import (
    TwilioConfigurationError,
    TwilioMediaError,
    download_twilio_recording_mp3,
)


router = APIRouter(
    prefix="/voice/twilio",
    tags=["Assistant vocal - Twilio"],
)


def _build_incoming_call_twiml(
    *,
    recording_action_url: str,
) -> str:
    safe_action_url = escape(
        recording_action_url,
        quote=True,
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="fr-FR">
        Bonjour, vous êtes en ligne avec le cabinet dentaire.
        Comment puis-je vous aider aujourd'hui ?
    </Say>
    <Record
        action="{safe_action_url}"
        method="POST"
        maxLength="30"
        timeout="3"
        playBeep="false"
        trim="trim-silence"
    />
    <Say language="fr-FR">
        Je n'ai entendu aucune réponse. Merci de rappeler le cabinet.
    </Say>
    <Hangup />
</Response>"""


def _build_terminal_twiml(
    message: str,
) -> str:
    safe_message = escape(
        message.strip(),
        quote=False,
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="fr-FR">
        {safe_message}
    </Say>
    <Hangup />
</Response>"""


def _build_conversation_reply_twiml(
    *,
    reply: str,
    recording_action_url: str,
    continue_call: bool,
) -> str:
    safe_reply = escape(
        reply.strip(),
        quote=False,
    )

    if not continue_call:
        return _build_terminal_twiml(safe_reply)

    safe_action_url = escape(
        recording_action_url,
        quote=True,
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="fr-FR">
        {safe_reply}
    </Say>
    <Record
        action="{safe_action_url}"
        method="POST"
        maxLength="30"
        timeout="3"
        playBeep="false"
        trim="trim-silence"
    />
    <Say language="fr-FR">
        Je n'ai entendu aucune réponse. Merci de rappeler le cabinet.
    </Say>
    <Hangup />
</Response>"""


@router.post(
    "/incoming",
    response_class=Response,
)
async def twilio_incoming_call(
    CallSid: str | None = Form(default=None),
    From: str | None = Form(default=None),
    To: str | None = Form(default=None),
) -> Response:
    """
    Reçoit un appel entrant Twilio et demande l'enregistrement
    du premier message du patient.

    La validation de signature Twilio sera ajoutée dans une étape
    séparée avant l'exposition publique du webhook.
    """

    twiml = _build_incoming_call_twiml(
        recording_action_url="/voice/twilio/recording",
    )

    return Response(
        content=twiml,
        media_type="application/xml",
        headers={
            "X-DentalFlow-Voice-Provider": "twilio",
            "X-DentalFlow-Call-Sid": CallSid or "",
            "X-DentalFlow-Caller": From or "",
            "X-DentalFlow-Called-Number": To or "",
        },
    )


@router.post(
    "/recording",
    response_class=Response,
)
async def twilio_recording(
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    RecordingUrl: str = Form(...),
    RecordingSid: str | None = Form(default=None),
    RecordingDuration: str | None = Form(default=None),
) -> Response:
    """
    Traite un tour vocal Twilio complet.

    Pipeline :
    enregistrement Twilio -> transcription -> DentalFlow -> TwiML
    """

    clinic = await find_active_clinic_by_voice_number(To)

    if clinic is None:
        twiml = _build_terminal_twiml(
            "Ce numéro n'est associé à aucun cabinet actif. "
            "Merci de vérifier le numéro appelé."
        )

        return Response(
            content=twiml,
            media_type="application/xml",
        )

    try:
        audio_content = await download_twilio_recording_mp3(
            RecordingUrl,
        )

        transcription = await transcribe_audio(
            filename=f"{RecordingSid or CallSid}.mp3",
            content=audio_content,
            language=clinic.get("language") or "fr",
        )

        conversation = ConversationInput(
            clinic_id=clinic["id"],
            channel="phone",
            sender_phone=From,
            message=transcription,
            external_id=RecordingSid,
            session_id=CallSid,
            metadata={
                "provider": "twilio",
                "input_source": "twilio_recording",
                "called_number": To,
                "recording_duration": RecordingDuration,
            },
        )

        result = await process_conversation(
            conversation,
        )

    except TwilioConfigurationError:
        twiml = _build_terminal_twiml(
            "Le service téléphonique est momentanément "
            "indisponible. Merci de rappeler le cabinet."
        )

        return Response(
            content=twiml,
            media_type="application/xml",
        )

    except (
        TwilioMediaError,
        VoiceTranscriptionError,
    ):
        twiml = _build_terminal_twiml(
            "Je n'ai pas pu comprendre votre message. "
            "Merci de rappeler le cabinet."
        )

        return Response(
            content=twiml,
            media_type="application/xml",
        )

    continue_call = (
        not result.requires_human
        and result.intent != "goodbye"
    )

    twiml = _build_conversation_reply_twiml(
        reply=result.reply,
        recording_action_url="/voice/twilio/recording",
        continue_call=continue_call,
    )

    return Response(
        content=twiml,
        media_type="application/xml",
        headers={
            "X-DentalFlow-Voice-Provider": "twilio",
            "X-DentalFlow-Call-Sid": CallSid,
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
