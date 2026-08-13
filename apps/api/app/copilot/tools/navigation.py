from app.copilot.tools.response import build_copilot_response

import re
import unicodedata


NAVIGATION_DESTINATIONS: tuple[dict[str, object], ...] = (
    {
        "name": "dashboard",
        "label": "le tableau de bord",
        "action_label": "Ouvrir le tableau de bord",
        "href": "/",
        "aliases": (
            "accueil",
            "tableau de bord",
            "dashboard",
            "page d'accueil",
        ),
    },
    {
        "name": "appointments",
        "label": "le calendrier",
        "action_label": "Ouvrir le calendrier",
        "href": "/appointments",
        "aliases": (
            "calendrier",
            "agenda",
            "planning",
            "rendez-vous",
            "rendez vous",
            "rdv",
        ),
    },
    {
        "name": "patients",
        "label": "la liste des patients",
        "action_label": "Ouvrir les patients",
        "href": "/patients",
        "aliases": (
            "patients",
            "liste des patients",
            "annuaire des patients",
        ),
    },
    {
        "name": "practitioners",
        "label": "la liste des praticiens",
        "action_label": "Ouvrir les praticiens",
        "href": "/practitioners",
        "aliases": (
            "praticiens",
            "praticiennes",
            "docteurs",
            "dentistes",
        ),
    },
    {
        "name": "treatments",
        "label": "la liste des soins",
        "action_label": "Ouvrir les soins",
        "href": "/treatments",
        "aliases": (
            "soins",
            "traitements",
            "actes",
        ),
    },
    {
        "name": "settings",
        "label": "les paramètres",
        "action_label": "Ouvrir les paramètres",
        "href": "/settings",
        "aliases": (
            "parametres",
            "paramètres",
            "reglages",
            "réglages",
            "configuration",
        ),
    },
    {
        "name": "copilot",
        "label": "le Copilote",
        "action_label": "Ouvrir le Copilote",
        "href": "/copilot",
        "aliases": (
            "copilote",
            "copilot",
            "assistant",
        ),
    },
)


def _normalize_navigation_text(
    value: str | None,
) -> str:
    normalized = (
        (value or "")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .strip()
        .lower()
    )

    normalized = "".join(
        character
        for character in unicodedata.normalize(
            "NFKD",
            normalized,
        )
        if not unicodedata.combining(character)
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized.strip()


def find_navigation_destination(
    message: str,
) -> dict[str, object] | None:
    normalized = _normalize_navigation_text(message)

    navigation_markers = (
        "ouvre",
        "ouvrir",
        "affiche",
        "afficher",
        "montre",
        "montrer",
        "va ",
        "aller ",
        "emmene",
        "amene",
        "accede",
        "acceder",
    )

    has_navigation_marker = any(
        marker in normalized
        for marker in navigation_markers
    )

    if not has_navigation_marker:
        return None

    for destination in NAVIGATION_DESTINATIONS:
        aliases = destination["aliases"]

        if any(
            _normalize_navigation_text(alias)
            in normalized
            for alias in aliases
        ):
            return destination

    return None


def looks_like_navigation(
    message: str,
) -> bool:
    return find_navigation_destination(message) is not None


async def answer_navigation(
    *,
    cur,
    clinic_id,
    message: str,
) -> dict:
    destination = find_navigation_destination(message)

    if destination is None:
        return build_copilot_response(
            answer=(
                "Je n’ai pas trouvé la page à ouvrir."
            ),
            intent="navigation",
            suggestions=[
                "Ouvrir les patients",
                "Ouvrir le calendrier",
                "Ouvrir les paramètres",
            ],
        )

    return build_copilot_response(
        answer=(
            f"Voici {destination['label']}."
        ),
        intent="navigation",
        actions=[
            {
                "type": "navigate",
                "label": destination["action_label"],
                "href": destination["href"],
            }
        ],
        suggestions=[
            "Qui vient aujourd’hui ?",
            "Ouvre la fiche de Ahmed Benali",
        ],
    )
