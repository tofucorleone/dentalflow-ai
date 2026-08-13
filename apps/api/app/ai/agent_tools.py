from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.ai.booking_availability import (
    find_available_slots_for_preference,
    find_available_slots_in_period,
)
from app.ai.llm.conversation_interpreter import (
    RequestedAgentTool,
)
from app.practitioner_service import list_practitioners
from app.treatment_service import list_active_treatments
from app.ai.time_preferences import (
    TimePreferenceError,
    parse_time_preference,
)


class AgentToolResult(BaseModel):
    name: str
    success: bool = True
    data: Any = None
    error: str | None = None


class AgentToolExecution(BaseModel):
    results: list[AgentToolResult] = Field(
        default_factory=list,
    )


def _normalize_search_text(
    value: str | None,
) -> str:
    return (
        value
        or ""
    ).strip().casefold()


async def _execute_list_practitioners(
    *,
    clinic_id: UUID,
) -> AgentToolResult:
    practitioners = await list_practitioners(
        clinic_id=clinic_id,
        include_inactive=False,
    )

    data = [
        {
            "id": practitioner["id"],
            "full_name": practitioner["full_name"],
            "speciality": practitioner.get("speciality"),
        }
        for practitioner in practitioners
    ]

    return AgentToolResult(
        name="list_practitioners",
        data=data,
    )


async def _execute_list_treatments(
    *,
    clinic_id: UUID,
) -> AgentToolResult:
    treatments = await list_active_treatments(
        clinic_id,
    )

    data = [
        {
            "id": treatment["id"],
            "name": treatment["name"],
            "description": treatment.get("description"),
            "duration_minutes": treatment.get(
                "duration_minutes"
            ),
            "price": treatment.get("price"),
            "requires_consultation": treatment.get(
                "requires_consultation"
            ),
        }
        for treatment in treatments
    ]

    return AgentToolResult(
        name="list_treatments",
        data=data,
    )


async def _execute_search_treatments(
    *,
    clinic_id: UUID,
    tool: RequestedAgentTool,
) -> AgentToolResult:
    treatments = await list_active_treatments(
        clinic_id,
    )

    query = _normalize_search_text(
        tool.treatment_text
        or tool.query
    )

    if not query:
        return AgentToolResult(
            name="search_treatments",
            success=False,
            data=[],
            error=(
                "Aucun soin à rechercher n'a été fourni."
            ),
        )

    matches = []

    for treatment in treatments:
        name = _normalize_search_text(
            treatment.get("name")
        )
        description = _normalize_search_text(
            treatment.get("description")
        )

        if (
            query in name
            or name in query
            or query in description
        ):
            matches.append(
                {
                    "id": treatment["id"],
                    "name": treatment["name"],
                    "description": treatment.get(
                        "description"
                    ),
                    "duration_minutes": treatment.get(
                        "duration_minutes"
                    ),
                    "price": treatment.get("price"),
                    "requires_consultation": treatment.get(
                        "requires_consultation"
                    ),
                }
            )

    return AgentToolResult(
        name="search_treatments",
        data={
            "query": (
                tool.treatment_text
                or tool.query
            ),
            "matches": matches,
        },
    )


async def _execute_find_available_slots(
    *,
    clinic_id: UUID,
    tool: RequestedAgentTool,
) -> AgentToolResult:
    date_text = (tool.date_text or "").strip()
    time_text = (tool.time_text or "").strip()

    if not date_text:
        return AgentToolResult(
            name="find_available_slots",
            success=False,
            data=[],
            error="Aucune date n'a été fournie.",
        )

    normalized_date_text = _normalize_search_text(
        date_text
    )

    is_period_search = normalized_date_text in {
        "cette semaine",
        "semaine courante",
        "la semaine courante",
        "la semaine prochaine",
        "semaine prochaine",
    }

    if not time_text and not is_period_search:
        return AgentToolResult(
            name="find_available_slots",
            success=False,
            data=[],
            error="Aucune préférence horaire n'a été fournie.",
        )

    preference = None

    if time_text:
        try:
            preference = parse_time_preference(time_text)
        except TimePreferenceError as exc:
            return AgentToolResult(
                name="find_available_slots",
                success=False,
                data=[],
                error=str(exc),
            )

    practitioners = await list_practitioners(
        clinic_id=clinic_id,
        include_inactive=False,
    )
    treatments = await list_active_treatments(clinic_id)

    practitioner_id = None
    treatment_id = None

    practitioner_query = _normalize_search_text(
        tool.practitioner_text
    )
    treatment_query = _normalize_search_text(
        tool.treatment_text
    )

    if practitioner_query:
        for practitioner in practitioners:
            if (
                _normalize_search_text(
                    practitioner.get("full_name")
                )
                == practitioner_query
            ):
                practitioner_id = practitioner["id"]
                break

        if practitioner_id is None:
            return AgentToolResult(
                name="find_available_slots",
                success=False,
                data=[],
                error="Le praticien demandé est introuvable.",
            )

    if treatment_query:
        for treatment in treatments:
            if (
                _normalize_search_text(
                    treatment.get("name")
                )
                == treatment_query
            ):
                treatment_id = treatment["id"]
                break

        if treatment_id is None:
            return AgentToolResult(
                name="find_available_slots",
                success=False,
                data=[],
                error="Le soin demandé est introuvable.",
            )

    if is_period_search:
        suggestions = await find_available_slots_in_period(
            clinic_id=clinic_id,
            period_text=date_text,
            preference=preference,
            practitioner_id=practitioner_id,
            treatment_id=treatment_id,
            limit=5,
        )
    else:
        suggestions = await find_available_slots_for_preference(
            clinic_id=clinic_id,
            date_text=date_text,
            preference=preference,
            practitioner_id=practitioner_id,
            treatment_id=treatment_id,
            limit=5,
        )

    practitioner_names = {
        practitioner["id"]: practitioner["full_name"]
        for practitioner in practitioners
    }

    slots = [
        {
            "practitioner_id": resolved_practitioner_id,
            "practitioner_name": practitioner_names.get(
                resolved_practitioner_id
            ),
            "start_at": start_at,
            "end_at": end_at,
            "date_label": start_at.strftime("%d/%m/%Y"),
            "time_label": start_at.strftime("%Hh%M"),
        }
        for resolved_practitioner_id, start_at, end_at
        in suggestions
    ]

    return AgentToolResult(
        name="find_available_slots",
        data={
            "date_text": date_text,
            "time_text": time_text,
            "practitioner_text": tool.practitioner_text,
            "treatment_text": tool.treatment_text,
            "slots": slots,
        },
    )


async def execute_requested_tools(
    *,
    clinic_id: UUID,
    requested_tools: list[RequestedAgentTool],
) -> AgentToolExecution:
    """
    Exécute uniquement des outils de lecture.

    Cette fonction ne réserve, ne déplace et n'annule
    jamais de rendez-vous.
    """

    results: list[AgentToolResult] = []

    for tool in requested_tools:
        try:
            if tool.name == "list_practitioners":
                result = await _execute_list_practitioners(
                    clinic_id=clinic_id,
                )

            elif tool.name == "list_treatments":
                result = await _execute_list_treatments(
                    clinic_id=clinic_id,
                )

            elif tool.name == "search_treatments":
                result = await _execute_search_treatments(
                    clinic_id=clinic_id,
                    tool=tool,
                )

            elif tool.name == "find_available_slots":
                result = await _execute_find_available_slots(
                    clinic_id=clinic_id,
                    tool=tool,
                )

            else:
                result = AgentToolResult(
                    name=tool.name,
                    success=False,
                    error=(
                        "Outil non encore pris en charge "
                        "par l'exécuteur."
                    ),
                )

        except Exception as exc:
            result = AgentToolResult(
                name=tool.name,
                success=False,
                error=str(exc),
            )

        results.append(result)

    return AgentToolExecution(
        results=results,
    )


__all__ = [
    "AgentToolExecution",
    "AgentToolResult",
    "execute_requested_tools",
]
