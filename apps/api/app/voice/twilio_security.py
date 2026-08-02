from collections.abc import Mapping

from fastapi import HTTPException, Request, status
from twilio.request_validator import RequestValidator

from app.config import get_settings


class TwilioSignatureConfigurationError(RuntimeError):
    """Configuration de validation Twilio absente."""


async def require_valid_twilio_signature(
    request: Request,
) -> None:
    """
    Refuse les webhooks dont la signature Twilio est invalide.

    La validation est ignorée lorsque l'option correspondante
    est désactivée dans la configuration.
    """

    form = await request.form()

    form_data = {
        key: str(value)
        for key, value in form.multi_items()
    }

    signature = request.headers.get(
        "X-Twilio-Signature",
    )

    try:
        is_valid = validate_twilio_signature(
            request_url=str(request.url),
            form_data=form_data,
            signature=signature,
        )
    except TwilioSignatureConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signature Twilio invalide.",
        )


def validate_twilio_signature(
    *,
    request_url: str,
    form_data: Mapping[str, str],
    signature: str | None,
) -> bool:
    """
    Valide la signature d'un webhook Twilio.

    Lorsque la validation est désactivée, retourne toujours True.
    """

    settings = get_settings()

    if not settings.twilio_signature_validation_enabled:
        return True

    if not settings.twilio_auth_token:
        raise TwilioSignatureConfigurationError(
            "TWILIO_AUTH_TOKEN doit être configuré lorsque "
            "la validation de signature Twilio est activée."
        )

    if not signature:
        return False

    validator = RequestValidator(
        settings.twilio_auth_token,
    )

    return validator.validate(
        request_url,
        dict(form_data),
        signature,
    )


__all__ = [
    "TwilioSignatureConfigurationError",
    "require_valid_twilio_signature",
    "validate_twilio_signature",
]
