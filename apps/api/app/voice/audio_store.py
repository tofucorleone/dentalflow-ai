from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


VOICE_AUDIO_ROOT = Path("/app/storage/voice/generated")
DEFAULT_AUDIO_TTL_SECONDS = 600


class VoiceAudioStoreError(RuntimeError):
    """Erreur pendant le stockage d'un fichier vocal temporaire."""


def _ensure_storage_root() -> None:
    VOICE_AUDIO_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )


def _audio_path(
    audio_id: str,
) -> Path:
    return VOICE_AUDIO_ROOT / f"{audio_id}.mp3"


def cleanup_expired_voice_audio(
    *,
    ttl_seconds: int = DEFAULT_AUDIO_TTL_SECONDS,
) -> int:
    """
    Supprime les fichiers MP3 plus anciens que le TTL demandé.

    Retourne le nombre de fichiers supprimés.
    """

    _ensure_storage_root()

    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=max(1, ttl_seconds),
    )

    deleted_count = 0

    for file_path in VOICE_AUDIO_ROOT.glob("*.mp3"):
        try:
            modified_at = datetime.fromtimestamp(
                file_path.stat().st_mtime,
                tz=timezone.utc,
            )
        except OSError:
            continue

        if modified_at >= cutoff:
            continue

        try:
            file_path.unlink()
        except OSError:
            continue

        deleted_count += 1

    return deleted_count


def store_voice_audio_mp3(
    content: bytes,
    *,
    ttl_seconds: int = DEFAULT_AUDIO_TTL_SECONDS,
) -> str:
    """
    Enregistre un MP3 temporaire et retourne son identifiant public.
    """

    if not content:
        raise VoiceAudioStoreError(
            "Le contenu audio à enregistrer est vide."
        )

    cleanup_expired_voice_audio(
        ttl_seconds=ttl_seconds,
    )

    audio_id = uuid4().hex
    destination = _audio_path(audio_id)

    try:
        destination.write_bytes(content)
    except OSError as exc:
        raise VoiceAudioStoreError(
            "Impossible d'enregistrer la réponse vocale."
        ) from exc

    return audio_id


def get_voice_audio_path(
    audio_id: str,
) -> Path | None:
    """
    Retourne le chemin du MP3 s'il existe.

    Seuls les identifiants hexadécimaux UUID générés par ce module
    sont acceptés.
    """

    cleaned_audio_id = audio_id.strip().lower()

    if (
        len(cleaned_audio_id) != 32
        or not all(
            character in "0123456789abcdef"
            for character in cleaned_audio_id
        )
    ):
        return None

    file_path = _audio_path(cleaned_audio_id)

    if not file_path.is_file():
        return None

    return file_path


__all__ = [
    "DEFAULT_AUDIO_TTL_SECONDS",
    "VOICE_AUDIO_ROOT",
    "VoiceAudioStoreError",
    "cleanup_expired_voice_audio",
    "get_voice_audio_path",
    "store_voice_audio_mp3",
]
