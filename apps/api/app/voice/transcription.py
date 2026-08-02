from openai import APIError

from app.ai.llm.client import (
    LlmConfigurationError,
    get_openai_client,
)


class VoiceTranscriptionError(RuntimeError):
    """Erreur pendant la transcription d'un fichier audio."""


SUPPORTED_AUDIO_EXTENSIONS = {
    ".flac",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".m4a",
    ".ogg",
    ".wav",
    ".webm",
}


async def transcribe_audio(
    *,
    filename: str,
    content: bytes,
    language: str | None = "fr",
) -> str:
    cleaned_filename = filename.strip()

    if not cleaned_filename:
        raise VoiceTranscriptionError(
            "Le nom du fichier audio est manquant."
        )

    if not content:
        raise VoiceTranscriptionError(
            "Le fichier audio est vide."
        )

    if len(content) > 25 * 1024 * 1024:
        raise VoiceTranscriptionError(
            "Le fichier audio dépasse la taille maximale autorisée."
        )

    try:
        client = get_openai_client()

        transcription = await client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=(
                cleaned_filename,
                content,
            ),
            language=language or "fr",
            response_format="json",
            prompt=(
                "Conversation téléphonique avec l'accueil "
                "d'un cabinet dentaire. "
                "Les échanges peuvent mentionner des rendez-vous, "
                "des horaires, des praticiens et des soins dentaires."
            ),
        )
    except LlmConfigurationError:
        raise
    except APIError as exc:
        raise VoiceTranscriptionError(
            "Le service de transcription vocale est indisponible."
        ) from exc

    text = getattr(
        transcription,
        "text",
        None,
    )

    if not isinstance(text, str) or not text.strip():
        raise VoiceTranscriptionError(
            "Aucune transcription exploitable n'a été retournée."
        )

    return text.strip()


__all__ = [
    "SUPPORTED_AUDIO_EXTENSIONS",
    "VoiceTranscriptionError",
    "transcribe_audio",
]
