from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.ai.processor import process_conversation
from app.ai.schemas import (
    ConversationInput,
    ConversationResult,
)
from app.deps import clinic_id
from app.ai.llm.client import LlmConfigurationError
from app.voice.audio_store import (
    get_voice_audio_path,
)
from app.voice.speech import (
    VoiceSpeechError,
    generate_speech_mp3,
)
from app.voice.transcription import (
    SUPPORTED_AUDIO_EXTENSIONS,
    VoiceTranscriptionError,
    transcribe_audio,
)


class VoiceSpeechRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=4000,
    )


class VoiceConversationRequest(BaseModel):
    sender_phone: str = Field(
        min_length=6,
        max_length=40,
    )

    message: str = Field(
        min_length=1,
        max_length=4000,
    )

    external_id: str | None = Field(
        default=None,
        max_length=255,
    )

    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )


router = APIRouter(
    prefix="/voice",
    tags=["Assistant vocal"],
)


@router.get(
    "/audio/{audio_id}",
    response_class=FileResponse,
)
async def get_generated_voice_audio(
    audio_id: str,
) -> FileResponse:
    """
    Sert un fichier MP3 temporaire généré par DentalFlow.
    """

    audio_path = get_voice_audio_path(audio_id)

    if audio_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier audio introuvable ou expiré.",
        )

    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
        filename=f"{audio_id}.mp3",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-AI-Generated-Voice": "true",
        },
    )


@router.post(
    "/speech/test",
    response_class=Response,
)
async def test_voice_speech(
    payload: VoiceSpeechRequest,
) -> Response:
    """
    Convertit un texte en fichier audio MP3.

    Cette route sert uniquement à valider la synthèse vocale
    avant le branchement au fournisseur téléphonique.
    """

    try:
        audio_content = await generate_speech_mp3(
            payload.text,
        )
    except LlmConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except VoiceSpeechError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return Response(
        content=audio_content,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": (
                'attachment; filename="dentalflow-voice.mp3"'
            ),
            "X-AI-Generated-Voice": "true",
        },
    )


@router.post(
    "/conversation/upload",
    response_class=Response,
)
async def voice_conversation_upload(
    sender_phone: str = Form(
        min_length=6,
        max_length=40,
    ),
    audio: UploadFile = File(...),
    external_id: str | None = Form(
        default=None,
        max_length=255,
    ),
    session_id: str | None = Form(
        default=None,
        min_length=1,
        max_length=255,
    ),
    language: str = Form(
        default="fr",
        min_length=2,
        max_length=10,
    ),
    current_clinic=Depends(clinic_id),
) -> Response:
    """
    Exécute un tour vocal complet à partir d'un fichier audio.

    Pipeline :
    audio -> transcription -> moteur DentalFlow -> réponse MP3
    """

    filename = audio.filename or "voice-input.webm"

    suffix = Path(filename).suffix.lower()

    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Format audio non pris en charge. "
                "Utilisez MP3, WAV, M4A, OGG, MP4, MPEG, FLAC ou WebM."
            ),
        )

    audio_content = await audio.read()

    try:
        transcription = await transcribe_audio(
            filename=filename,
            content=audio_content,
            language=language,
        )
    except LlmConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except VoiceTranscriptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    conversation = ConversationInput(
        clinic_id=current_clinic,
        channel="phone",
        sender_phone=sender_phone,
        message=transcription,
        external_id=external_id,
        session_id=session_id or external_id,
        metadata={
            "input_source": "voice_upload",
            "audio_filename": filename,
            "transcription_language": language,
        },
    )

    result = await process_conversation(conversation)

    try:
        reply_audio = await generate_speech_mp3(
            result.reply,
        )
    except LlmConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except VoiceSpeechError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    safe_transcription = (
        transcription
        .replace("\r", " ")
        .replace("\n", " ")
    )[:500]

    return Response(
        content=reply_audio,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": (
                'attachment; filename="dentalflow-voice-reply.mp3"'
            ),
            "X-AI-Generated-Voice": "true",
            "X-DentalFlow-Intent": result.intent,
            "X-DentalFlow-Requires-Human": (
                "true"
                if result.requires_human
                else "false"
            ),
            "X-DentalFlow-Patient-Id": (
                str(result.patient_id)
                if result.patient_id is not None
                else ""
            ),
            "X-DentalFlow-Transcription": safe_transcription,
        },
    )


@router.post(
    "/conversation/audio",
    response_class=Response,
)
async def voice_conversation_audio(
    payload: VoiceConversationRequest,
    current_clinic=Depends(clinic_id),
) -> Response:
    """
    Exécute un tour conversationnel téléphonique complet.

    Entrée :
    - transcription texte du patient

    Sortie :
    - réponse DentalFlow convertie en MP3
    """

    conversation = ConversationInput(
        clinic_id=current_clinic,
        channel="phone",
        sender_phone=payload.sender_phone,
        message=payload.message,
        external_id=payload.external_id,
        session_id=(
            payload.session_id
            or payload.external_id
        ),
        metadata={
            **payload.metadata,
            "input_source": "voice_transcript",
        },
    )

    result = await process_conversation(conversation)

    try:
        audio_content = await generate_speech_mp3(
            result.reply,
        )
    except LlmConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except VoiceSpeechError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return Response(
        content=audio_content,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": (
                'attachment; filename="dentalflow-reply.mp3"'
            ),
            "X-AI-Generated-Voice": "true",
            "X-DentalFlow-Intent": result.intent,
            "X-DentalFlow-Requires-Human": (
                "true"
                if result.requires_human
                else "false"
            ),
            "X-DentalFlow-Patient-Id": (
                str(result.patient_id)
                if result.patient_id is not None
                else ""
            ),
        },
    )


@router.post(
    "/conversation/test",
    response_model=ConversationResult,
)
async def test_voice_conversation(
    payload: VoiceConversationRequest,
    current_clinic=Depends(clinic_id),
) -> ConversationResult:
    """
    Simule une transcription issue d'un appel téléphonique.

    L'audio et le fournisseur téléphonique seront branchés plus tard.
    Le moteur conversationnel DentalFlow reste inchangé.
    """

    conversation = ConversationInput(
        clinic_id=current_clinic,
        channel="phone",
        sender_phone=payload.sender_phone,
        message=payload.message,
        external_id=payload.external_id,
        session_id=(
            payload.session_id
            or payload.external_id
        ),
        metadata={
            **payload.metadata,
            "input_source": "voice_transcript",
        },
    )

    return await process_conversation(conversation)


__all__ = [
    "VoiceConversationRequest",
    "VoiceSpeechRequest",
    "router",
    "voice_conversation_audio",
    "voice_conversation_upload",
]
