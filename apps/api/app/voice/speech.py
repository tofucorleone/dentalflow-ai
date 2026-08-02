from openai import APIError

from app.ai.llm.client import (
    LlmConfigurationError,
    get_openai_client,
)


class VoiceSpeechError(RuntimeError):
    """Erreur pendant la génération de la réponse vocale."""


async def generate_speech_mp3(
    text: str,
) -> bytes:
    cleaned_text = text.strip()

    if not cleaned_text:
        raise VoiceSpeechError(
            "Le texte à convertir en audio est vide."
        )

    if len(cleaned_text) > 4000:
        raise VoiceSpeechError(
            "Le texte à convertir en audio est trop long."
        )

    try:
        client = get_openai_client()

        response = await client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="marin",
            input=cleaned_text,
            instructions=(
                "Parle en français avec une voix professionnelle, "
                "chaleureuse, calme et naturelle. "
                "Tu représentes l'accueil d'un cabinet dentaire."
            ),
            response_format="mp3",
        )

        audio_content = response.content

    except LlmConfigurationError:
        raise
    except APIError as exc:
        raise VoiceSpeechError(
            "Le service de synthèse vocale est indisponible."
        ) from exc

    if not audio_content:
        raise VoiceSpeechError(
            "Le service vocal n'a retourné aucun contenu audio."
        )

    return audio_content


__all__ = [
    "VoiceSpeechError",
    "generate_speech_mp3",
]
