import asyncio
from urllib.parse import urlparse

import httpx

from app.config import get_settings


class TwilioConfigurationError(RuntimeError):
    """Configuration Twilio absente ou invalide."""


class TwilioMediaError(RuntimeError):
    """Erreur pendant le téléchargement d'un média Twilio."""


def _validate_recording_url(recording_url: str) -> str:
    cleaned_url = recording_url.strip()

    if not cleaned_url:
        raise TwilioMediaError(
            "L'URL de l'enregistrement Twilio est manquante."
        )

    parsed_url = urlparse(cleaned_url)

    if parsed_url.scheme != "https":
        raise TwilioMediaError(
            "L'URL de l'enregistrement Twilio doit utiliser HTTPS."
        )

    hostname = (parsed_url.hostname or "").lower()

    allowed_hosts = (
        "api.twilio.com",
        "api.twilio.com.cn",
    )

    if hostname not in allowed_hosts:
        raise TwilioMediaError(
            "Le domaine de l'enregistrement Twilio n'est pas autorisé."
        )

    if cleaned_url.lower().endswith(".mp3"):
        return cleaned_url

    return f"{cleaned_url}.mp3"


async def download_twilio_recording_mp3(
    recording_url: str,
) -> bytes:
    """
    Télécharge un enregistrement Twilio au format MP3.

    Quelques tentatives sont effectuées car le média peut ne pas être
    immédiatement disponible lors du callback d'enregistrement.
    """

    settings = get_settings()

    if (
        not settings.twilio_account_sid
        or not settings.twilio_auth_token
    ):
        raise TwilioConfigurationError(
            "TWILIO_ACCOUNT_SID et TWILIO_AUTH_TOKEN "
            "doivent être configurés."
        )

    media_url = _validate_recording_url(recording_url)

    attempts = max(
        1,
        settings.twilio_recording_download_attempts,
    )

    timeout = httpx.Timeout(
        settings.twilio_recording_download_timeout,
    )

    auth = httpx.BasicAuth(
        settings.twilio_account_sid,
        settings.twilio_auth_token,
    )

    async with httpx.AsyncClient(
        auth=auth,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        for attempt in range(1, attempts + 1):
            try:
                response = await client.get(media_url)
            except httpx.HTTPError as exc:
                if attempt == attempts:
                    raise TwilioMediaError(
                        "Impossible de télécharger "
                        "l'enregistrement Twilio."
                    ) from exc
            else:
                if response.status_code == 200:
                    content = response.content

                    if not content:
                        raise TwilioMediaError(
                            "L'enregistrement Twilio est vide."
                        )

                    return content

                if response.status_code not in {
                    404,
                    409,
                    425,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise TwilioMediaError(
                        "Twilio a refusé l'accès à "
                        f"l'enregistrement ({response.status_code})."
                    )

                if attempt == attempts:
                    raise TwilioMediaError(
                        "L'enregistrement Twilio n'est pas "
                        "encore disponible."
                    )

            await asyncio.sleep(min(attempt, 3))

    raise TwilioMediaError(
        "L'enregistrement Twilio n'a pas pu être téléchargé."
    )


__all__ = [
    "TwilioConfigurationError",
    "TwilioMediaError",
    "download_twilio_recording_mp3",
]
