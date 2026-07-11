import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings


SCOPES = ["https://www.googleapis.com/auth/calendar"]
settings = get_settings()


class CalendarConfigurationError(RuntimeError):
    pass


class CalendarOperationError(RuntimeError):
    pass


def _service():
    if not settings.google_calendar_enabled:
        raise CalendarConfigurationError(
            "Google Calendar n’est pas activé dans la configuration."
        )

    credentials_path = Path(settings.google_service_account_file)
    if not credentials_path.is_file():
        raise CalendarConfigurationError(
            f"Fichier du compte de service introuvable : {credentials_path}"
        )

    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _event_body(
    *,
    patient_name: str | None,
    patient_phone: str,
    treatment_name: str | None,
    practitioner_name: str | None,
    start_at: datetime,
    end_at: datetime,
    timezone_name: str,
    appointment_id: str,
) -> dict[str, Any]:
    patient_label = patient_name or patient_phone
    treatment_label = treatment_name or "Consultation"

    return {
        "summary": f"RDV Dentaire - {patient_label} - {treatment_label}",
        "description": (
            f"Patient : {patient_label}\n"
            f"Téléphone : {patient_phone}\n"
            f"Soin : {treatment_label}\n"
            f"Praticien : {practitioner_name or 'Non précisé'}\n"
            f"Référence DentalFlow : {appointment_id}"
        ),
        "start": {
            "dateTime": start_at.isoformat(),
            "timeZone": timezone_name,
        },
        "end": {
            "dateTime": end_at.isoformat(),
            "timeZone": timezone_name,
        },
    }


def _create_sync(calendar_id: str, body: dict[str, Any]) -> dict:
    try:
        return (
            _service()
            .events()
            .insert(calendarId=calendar_id, body=body)
            .execute()
        )
    except HttpError as exc:
        raise CalendarOperationError(
            f"Échec de création Google Calendar : {exc}"
        ) from exc


def _update_sync(calendar_id: str, event_id: str, body: dict[str, Any]) -> dict:
    try:
        return (
            _service()
            .events()
            .update(calendarId=calendar_id, eventId=event_id, body=body)
            .execute()
        )
    except HttpError as exc:
        raise CalendarOperationError(
            f"Échec de modification Google Calendar : {exc}"
        ) from exc


def _delete_sync(calendar_id: str, event_id: str) -> None:
    try:
        (
            _service()
            .events()
            .delete(calendarId=calendar_id, eventId=event_id)
            .execute()
        )
    except HttpError as exc:
        # 404 means the event is already absent; cancellation remains idempotent.
        if getattr(exc, "status_code", None) == 404 or getattr(exc.resp, "status", None) == 404:
            return
        raise CalendarOperationError(
            f"Échec de suppression Google Calendar : {exc}"
        ) from exc


async def create_event(calendar_id: str, body: dict[str, Any]) -> dict:
    return await asyncio.to_thread(_create_sync, calendar_id, body)


async def update_event(
    calendar_id: str,
    event_id: str,
    body: dict[str, Any],
) -> dict:
    return await asyncio.to_thread(_update_sync, calendar_id, event_id, body)


async def delete_event(calendar_id: str, event_id: str) -> None:
    await asyncio.to_thread(_delete_sync, calendar_id, event_id)


def make_event_body(**kwargs) -> dict[str, Any]:
    return _event_body(**kwargs)
