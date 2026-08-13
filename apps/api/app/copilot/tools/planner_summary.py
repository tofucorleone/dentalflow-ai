import unicodedata

from app.copilot.planner import build_planner
from app.copilot.tools.response import (
    build_copilot_response,
)


def _normalize_planner_text(
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

    return "".join(
        character
        for character in unicodedata.normalize(
            "NFKD",
            normalized,
        )
        if not unicodedata.combining(character)
    )


def looks_like_planner_summary(
    message: str,
) -> bool:
    normalized = _normalize_planner_text(message)

    exact_or_strong_markers = (
        "que dois-je faire",
        "que dois je faire",
        "quoi faire aujourd'hui",
        "quoi faire aujourdhui",
        "mes priorites",
        "les priorites du jour",
        "priorites aujourd'hui",
        "priorites aujourdhui",
        "actions prioritaires",
        "actions du jour",
        "prepare ma journee",
        "prepare-moi ma journee",
        "resume ma journee",
        "organise ma journee",
        "par quoi commencer",
    )

    return any(
        marker in normalized
        for marker in exact_or_strong_markers
    )


def _priority_label(
    priority: str,
) -> str:
    labels = {
        "high": "priorité haute",
        "medium": "priorité moyenne",
        "low": "priorité basse",
    }

    return labels.get(
        priority,
        "priorité non définie",
    )


async def answer_planner_summary(
    *,
    cur,
    clinic_id,
    message: str,
) -> dict:
    planner = await build_planner(
        cur=cur,
        clinic_id=clinic_id,
    )

    recommended_actions = (
        planner.get("recommended_actions")
        or []
    )

    if not recommended_actions:
        return build_copilot_response(
            answer=(
                "Aucune action prioritaire n’est détectée "
                "pour le moment. Le planning et le suivi "
                "préventif ne nécessitent pas d’intervention "
                "immédiate."
            ),
            intent="planner_summary",
            actions=[
                {
                    "type": "navigate",
                    "label": "Ouvrir le Copilote",
                    "href": "/copilot",
                },
                {
                    "type": "navigate",
                    "label": "Ouvrir le calendrier",
                    "href": "/appointments",
                },
            ],
            suggestions=[
                "Qui vient aujourd’hui ?",
                "Qui vient demain ?",
                "Qui dois-je rappeler ?",
            ],
        )

    visible_actions = recommended_actions[:6]
    answer_lines: list[str] = []
    navigation_actions: list[dict] = []

    for index, recommendation in enumerate(
        visible_actions,
        start=1,
    ):
        title = recommendation["title"]
        description = recommendation["description"]
        score = recommendation["score"]
        priority = _priority_label(
            recommendation["priority"]
        )

        answer_lines.append(
            f"{index}. {title} — {description} "
            f"({priority}, score {score})"
        )

        for action in recommendation.get(
            "actions"
        ) or []:
            candidate = {
                "type": action["type"],
                "label": action["label"],
                "href": action["href"],
            }

            if candidate not in navigation_actions:
                navigation_actions.append(
                    candidate
                )

    total = len(recommended_actions)

    if total == 1:
        introduction = (
            "Voici l’action prioritaire détectée "
            "pour aujourd’hui."
        )
    else:
        introduction = (
            f"Voici les {total} actions prioritaires "
            "détectées pour aujourd’hui."
        )

    answer_parts = [
        introduction,
        "",
        *answer_lines,
    ]

    if total > len(visible_actions):
        remaining = total - len(visible_actions)

        answer_parts.extend(
            [
                "",
                (
                    f"Et {remaining} autre"
                    f"{'s' if remaining > 1 else ''} "
                    "action"
                    f"{'s' if remaining > 1 else ''} "
                    "dans le Planner."
                ),
            ]
        )

    return build_copilot_response(
        answer="\n".join(answer_parts),
        intent="planner_summary",
        actions=navigation_actions,
        sources=[],
        suggestions=[
            "Qui dois-je rappeler ?",
            "Qui vient aujourd’hui ?",
            "Qui vient demain ?",
            "Ouvrir le Copilote",
        ],
        requires_validation=False,
    )
