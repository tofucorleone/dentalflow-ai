from app.copilot.schemas import (
    CopilotTaskStateUpdateRequest,
)


def test_task_state_update_accepts_prepared():
    payload = CopilotTaskStateUpdateRequest(
        status="prepared",
    )

    assert payload.status == "prepared"
    assert payload.snoozed_until is None
    assert payload.assign_to_me is False
