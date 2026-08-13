import hashlib
import hmac

from fastapi import HTTPException, status

from app.db import connection
from app.integrations.repository import (
    get_active_integration,
)


async def resolve_active_integration(
    *,
    provider: str,
    provider_instance: str,
    supplied_secret: str | None,
) -> dict:
    normalized_provider = provider.strip().lower()
    normalized_instance = provider_instance.strip()

    if not normalized_provider:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le fournisseur est obligatoire.",
        )

    if not normalized_instance:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="L’instance fournisseur est obligatoire.",
        )

    async with connection() as conn:
        async with conn.cursor() as cur:
            integration = await get_active_integration(
                cur=cur,
                provider=normalized_provider,
                provider_instance=normalized_instance,
            )

    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Aucune intégration active ne correspond "
                "au fournisseur et à l’instance."
            ),
        )

    expected_hash = str(
        integration.get("provider_token_hash") or ""
    ).strip().lower()

    if not expected_hash:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Aucun token webhook n’est configuré "
                "pour cette intégration."
            ),
        )

    candidate_secret = supplied_secret or ""

    if not candidate_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Secret d’intégration absent.",
        )

    candidate_hash = hashlib.sha256(
        candidate_secret.encode("utf-8")
    ).hexdigest()

    if not hmac.compare_digest(
        candidate_hash,
        expected_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Secret d’intégration invalide.",
        )

    return integration


__all__ = ["resolve_active_integration"]
