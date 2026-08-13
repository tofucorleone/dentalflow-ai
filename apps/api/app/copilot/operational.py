from datetime import datetime


def build_priorities(
    *,
    appointments: list[dict],
    now: datetime,
) -> dict:
    pending_confirmation = 0
    cancelled_today = 0
    no_show = 0
    late_active = 0

    for appointment in appointments:
        appointment_status = appointment.get("status")
        start_at = appointment.get("start_at")

        if (
            appointment_status == "pending"
            and start_at is not None
            and start_at >= now
        ):
            pending_confirmation += 1

        if appointment_status == "cancelled":
            cancelled_today += 1

        if appointment_status == "no_show":
            no_show += 1

        if (
            appointment_status in {"pending", "confirmed"}
            and start_at is not None
            and start_at < now
        ):
            late_active += 1

    return {
        "pending_confirmation": pending_confirmation,
        "cancelled_today": cancelled_today,
        "no_show": no_show,
        "late_active": late_active,
    }


def build_released_slots(
    *,
    appointments: list[dict],
) -> list[dict]:
    released_slots = [
        {
            "appointment_id": appointment["id"],
            "cancelled_patient_id": appointment["patient_id"],
            "practitioner_id": appointment.get("practitioner_id"),
            "practitioner_name": appointment.get("practitioner_name"),
            "treatment_id": appointment.get("treatment_id"),
            "start_at": appointment["start_at"],
            "end_at": appointment["end_at"],
        }
        for appointment in appointments
        if (
            appointment.get("status") == "cancelled"
            and appointment.get("start_at") is not None
            and appointment.get("end_at") is not None
        )
    ]

    return sorted(
        released_slots,
        key=lambda slot: slot["start_at"],
    )
