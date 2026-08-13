from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.copilot.tools.navigation import (
    answer_navigation,
    looks_like_navigation,
)

from app.copilot.tools.patient import (
    answer_patient_lookup,
    looks_like_patient_lookup,
)

from app.copilot.tools.patient_next_appointment import (
    answer_next_patient_appointment,
    looks_like_next_patient_appointment,
)
from app.copilot.tools.practitioner import (
    answer_next_practitioner_appointment,
    looks_like_next_practitioner_appointment,
)

from app.copilot.tools.planner_summary import (
    answer_planner_summary,
    looks_like_planner_summary,
)

from app.copilot.tools.recall import (
    answer_recall_patients,
    looks_like_recall_patients,
)

from app.copilot.tools.schedule import (
    answer_schedule,
    looks_like_schedule,
)


CopilotToolMatcher = Callable[[str], bool]
CopilotToolExecutor = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class CopilotTool:
    name: str
    matches: CopilotToolMatcher
    execute: CopilotToolExecutor


COPILOT_TOOLS: tuple[CopilotTool, ...] = (
    CopilotTool(
        name="next_practitioner_appointment",
        matches=looks_like_next_practitioner_appointment,
        execute=answer_next_practitioner_appointment,
    ),
    CopilotTool(
        name="patient_next_appointment",
        matches=looks_like_next_patient_appointment,
        execute=answer_next_patient_appointment,
    ),
    CopilotTool(
        name="planner_summary",
        matches=looks_like_planner_summary,
        execute=answer_planner_summary,
    ),
    CopilotTool(
        name="recall",
        matches=looks_like_recall_patients,
        execute=answer_recall_patients,
    ),
    CopilotTool(
        name="schedule",
        matches=looks_like_schedule,
        execute=answer_schedule,
    ),
    CopilotTool(
        name="navigation",
        matches=looks_like_navigation,
        execute=answer_navigation,
    ),
    CopilotTool(
        name="patient_lookup",
        matches=looks_like_patient_lookup,
        execute=answer_patient_lookup,
    ),
)


def find_copilot_tool(
    message: str,
) -> CopilotTool | None:
    for tool in COPILOT_TOOLS:
        if tool.matches(message):
            return tool

    return None


async def execute_copilot_tool(
    *,
    cur,
    clinic_id,
    message: str,
) -> dict[str, Any] | None:
    tool = find_copilot_tool(message)

    if tool is None:
        return None

    return await tool.execute(
        cur=cur,
        clinic_id=clinic_id,
        message=message,
    )
