import re

from app.ai.booking_datetime import normalize_text


POSITIVE_CONFIRMATIONS = {
    "oui",
    "oui merci",
    "oui je confirme",
    "je confirme",
    "confirmer",
    "confirme",
    "d accord",
    "daccord",
    "c est bon",
    "cest bon",
    "ok",
    "okay",
}

NEGATIVE_CONFIRMATIONS = {
    "non",
    "non merci",
    "annuler",
    "annule",
    "je refuse",
    "pas d accord",
    "pas daccord",
    "je ne confirme pas",
    "ne confirme pas",
}


def parse_confirmation(message: str) -> bool | None:
    """
    Analyse une réponse conversationnelle de confirmation.

    Retourne :
    - True pour une confirmation positive ;
    - False pour une confirmation négative ;
    - None lorsque la réponse est ambiguë.
    """
    normalized = normalize_text(message)

    normalized = re.sub(
        r"[^a-z0-9\s]",
        " ",
        normalized,
    )
    normalized = " ".join(normalized.split())

    if normalized in NEGATIVE_CONFIRMATIONS:
        return False

    if normalized in POSITIVE_CONFIRMATIONS:
        return True

    return None
