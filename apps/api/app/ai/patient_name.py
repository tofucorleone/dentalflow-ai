import re


_NAME_TOKEN_RE = re.compile(
    r"^[A-Za-zÀ-ÖØ-öø-ÿŒœÆæÇç]+(?:[-'][A-Za-zÀ-ÖØ-öø-ÿŒœÆæÇç]+)*$"
)

_PREFIXES = (
    "je m'appelle ",
    "je m appelle ",
    "mon nom est ",
    "moi c'est ",
    "moi c est ",
)


def extract_patient_name(message: str) -> str | None:
    """
    Retourne uniquement un nom/prénom suffisamment crédible.

    Cette fonction est volontairement stricte :
    une phrase conversationnelle ne doit jamais devenir un nom patient.
    """
    cleaned = " ".join(message.strip().split())

    if not cleaned:
        return None

    if len(cleaned) > 100:
        return None

    # Une question ou une phrase manifestement conversationnelle
    # ne doit jamais devenir un nom.
    if any(char in cleaned for char in ("?", "!", ":", ";")):
        return None

    lowered = cleaned.casefold()

    for prefix in _PREFIXES:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            lowered = cleaned.casefold()
            break

    # Expressions indiquant clairement qu'il ne s'agit pas d'un nom.
    forbidden_starts = (
        "je pense",
        "je crois",
        "je veux",
        "je voudrais",
        "j'aimerais",
        "j aimerais",
        "je préfère",
        "je prefere",
        "je peux",
        "je suis",
        "vous êtes",
        "vous etes",
        "est-ce",
        "est ce",
        "pourquoi",
        "comment",
        "quand",
        "quel",
        "quelle",
        "bonjour",
        "bonsoir",
        "salut",
        "merci",
        "oui",
        "non",
        "d'accord",
        "d accord",
        "demain",
        "aujourd'hui",
        "aujourd hui",
    )

    lowered = cleaned.casefold()

    if any(
        lowered == prefix
        or lowered.startswith(prefix + " ")
        for prefix in forbidden_starts
    ):
        return None

    tokens = cleaned.split()

    # On exige nom + prénom au minimum.
    # Les noms composés restent possibles.
    if len(tokens) < 2 or len(tokens) > 6:
        return None

    if not all(_NAME_TOKEN_RE.fullmatch(token) for token in tokens):
        return None

    # Évite des valeurs absurdes constituées de mots d'une seule lettre.
    if sum(len(token.replace("-", "").replace("'", "")) for token in tokens) < 4:
        return None

    return " ".join(
        token[:1].upper() + token[1:]
        for token in tokens
    )


def is_valid_patient_name(message: str) -> bool:
    return extract_patient_name(message) is not None
