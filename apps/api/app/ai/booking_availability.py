from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from uuid import UUID

from fastapi import HTTPException

from app.ai.booking_datetime import (
    normalize_text,
    parse_booking_date,
    parse_booking_datetime,
)
from app.ai.time_preferences import TimePreference
from app.appointment_service import (
    clinic_timezone,
    validate_appointment_slot,
)
from app.db import connection


async def check_booking_availability(
    clinic_id: UUID,
    date_text: str,
    time_text: str,
    practitioner_id: UUID | None = None,
    treatment_id: UUID | None = None,
    exclude_appointment_id: UUID | None = None,
) -> tuple[UUID, datetime, datetime]:
    async with connection() as conn:
        async with conn.cursor() as cur:
            timezone_name = await clinic_timezone(
                cur,
                clinic_id,
            )

            start_at = parse_booking_datetime(
                date_text=date_text,
                time_text=time_text,
                timezone_name=timezone_name,
            )

            resolved_practitioner, end_at = (
                await validate_appointment_slot(
                    cur=cur,
                    clinic_id=clinic_id,
                    practitioner_id=practitioner_id,
                    treatment_id=treatment_id,
                    start_at=start_at,
                    end_at=None,
                    exclude_appointment_id=exclude_appointment_id,
                )
            )

            return (
                resolved_practitioner,
                start_at,
                end_at,
            )


async def find_next_available_slots(
    clinic_id: UUID,
    date_text: str,
    time_text: str,
    practitioner_id: UUID | None = None,
    treatment_id: UUID | None = None,
    limit: int = 3,
    step_minutes: int = 60,
) -> list[tuple[UUID, datetime, datetime]]:
    timezone_name: str

    async with connection() as conn:
        async with conn.cursor() as cur:
            timezone_name = await clinic_timezone(
                cur,
                clinic_id,
            )

            requested_start = parse_booking_datetime(
                date_text=date_text,
                time_text=time_text,
                timezone_name=timezone_name,
            )

            suggestions: list[
                tuple[UUID, datetime, datetime]
            ] = []

            candidate_start = requested_start.replace(
                minute=0,
                second=0,
                microsecond=0,
            )

            for _ in range(24):
                candidate_start = candidate_start + timedelta(
                    minutes=step_minutes,
                )

                try:
                    resolved_practitioner, end_at = (
                        await validate_appointment_slot(
                            cur=cur,
                            clinic_id=clinic_id,
                            practitioner_id=practitioner_id,
                            treatment_id=treatment_id,
                            start_at=candidate_start,
                            end_at=None,
                        )
                    )
                except HTTPException:
                    continue

                suggestions.append(
                    (
                        resolved_practitioner,
                        candidate_start,
                        end_at,
                    )
                )

                if len(suggestions) >= limit:
                    break

            return suggestions


async def find_available_slots_for_preference(
    clinic_id: UUID,
    date_text: str,
    preference: TimePreference,
    practitioner_id: UUID | None = None,
    treatment_id: UUID | None = None,
    exclude_appointment_id: UUID | None = None,
    limit: int = 3,
    step_minutes: int = 60,
) -> list[tuple[UUID, datetime, datetime]]:
    if limit <= 0:
        return []

    if step_minutes <= 0:
        raise ValueError("step_minutes doit être supérieur à zéro.")

    async with connection() as conn:
        async with conn.cursor() as cur:
            timezone_name = await clinic_timezone(
                cur,
                clinic_id,
            )
            timezone = ZoneInfo(timezone_name)
            current = datetime.now(timezone)

            requested_date = parse_booking_date(
                date_text=date_text,
                current=current,
            )

            if preference.exact_time is not None:
                range_start = preference.exact_time
                range_end = preference.exact_time
            else:
                range_start = preference.earliest or time(0, 0)
                range_end = preference.latest or time(23, 59)

            candidate_start = datetime.combine(
                requested_date,
                range_start,
                tzinfo=timezone,
            )

            if (
                preference.exact_time is None
                and (
                    candidate_start.minute != 0
                    or candidate_start.second != 0
                    or candidate_start.microsecond != 0
                )
            ):
                candidate_start = (
                    candidate_start + timedelta(hours=1)
                ).replace(
                    minute=0,
                    second=0,
                    microsecond=0,
                )

            latest_start = datetime.combine(
                requested_date,
                range_end,
                tzinfo=timezone,
            )

            if preference.exact_time is None and candidate_start <= current:
                elapsed_minutes = (
                    current - candidate_start
                ).total_seconds() / 60

                steps_to_skip = int(
                    elapsed_minutes // step_minutes,
                ) + 1

                candidate_start += timedelta(
                    minutes=steps_to_skip * step_minutes,
                )

            if practitioner_id is not None:
                practitioner_ids = [practitioner_id]
            elif treatment_id is not None:
                await cur.execute(
                    """
                    SELECT p.id
                    FROM practitioners p
                    JOIN practitioner_treatments pt
                      ON pt.practitioner_id = p.id
                    WHERE p.clinic_id = %s
                      AND p.active = TRUE
                      AND pt.treatment_id = %s
                    ORDER BY p.full_name
                    """,
                    (
                        clinic_id,
                        treatment_id,
                    ),
                )
                practitioner_ids = [
                    row["id"]
                    for row in await cur.fetchall()
                ]
            else:
                await cur.execute(
                    """
                    SELECT id
                    FROM practitioners
                    WHERE clinic_id = %s
                      AND active = TRUE
                    ORDER BY full_name
                    """,
                    (clinic_id,),
                )
                practitioner_ids = [
                    row["id"]
                    for row in await cur.fetchall()
                ]

            suggestions: list[
                tuple[UUID, datetime, datetime]
            ] = []

            while candidate_start <= latest_start:
                if candidate_start > current:
                    for candidate_practitioner_id in practitioner_ids:
                        try:
                            resolved_practitioner, end_at = (
                                await validate_appointment_slot(
                                    cur=cur,
                                    clinic_id=clinic_id,
                                    practitioner_id=(
                                        candidate_practitioner_id
                                    ),
                                    treatment_id=treatment_id,
                                    start_at=candidate_start,
                                    end_at=None,
                                    exclude_appointment_id=(
                                        exclude_appointment_id
                                    ),
                                )
                            )
                        except HTTPException:
                            continue

                        if (
                            preference.latest is not None
                            and end_at.astimezone(timezone).time()
                            > preference.latest
                        ):
                            continue

                        suggestions.append(
                            (
                                resolved_practitioner,
                                candidate_start,
                                end_at,
                            )
                        )
                        break

                    if len(suggestions) >= limit:
                        break

                if preference.exact_time is not None:
                    break

                candidate_start += timedelta(
                    minutes=step_minutes,
                )

            return suggestions

async def find_available_slots_in_period(
    clinic_id: UUID,
    period_text: str,
    preference: TimePreference | None = None,
    practitioner_id: UUID | None = None,
    treatment_id: UUID | None = None,
    exclude_appointment_id: UUID | None = None,
    limit: int = 5,
    step_minutes: int = 60,
) -> list[tuple[UUID, datetime, datetime]]:
    """
    Recherche les premiers créneaux disponibles sur une période.

    Périodes actuellement acceptées :
    - cette semaine ;
    - la semaine prochaine.

    Cette fonction est strictement en lecture seule.
    """

    if limit <= 0:
        return []

    if step_minutes <= 0:
        raise ValueError(
            "step_minutes doit être supérieur à zéro."
        )

    normalized_period = normalize_text(period_text)

    async with connection() as conn:
        async with conn.cursor() as cur:
            timezone_name = await clinic_timezone(
                cur,
                clinic_id,
            )
            timezone = ZoneInfo(timezone_name)
            current = datetime.now(timezone)

            if normalized_period in {
                "cette semaine",
                "semaine courante",
                "la semaine courante",
            }:
                start_date = current.date()
                end_date = start_date + timedelta(
                    days=6 - start_date.weekday(),
                )

            elif normalized_period in {
                "la semaine prochaine",
                "semaine prochaine",
            }:
                days_until_monday = (
                    7 - current.date().weekday()
                )
                start_date = current.date() + timedelta(
                    days=days_until_monday,
                )
                end_date = start_date + timedelta(days=6)

            else:
                raise ValueError(
                    "La période doit être « cette semaine » "
                    "ou « la semaine prochaine »."
                )

            if preference is None:
                range_start = time(0, 0)
                range_end = time(23, 59)
            elif preference.exact_time is not None:
                range_start = preference.exact_time
                range_end = preference.exact_time
            else:
                range_start = (
                    preference.earliest
                    or time(0, 0)
                )
                range_end = (
                    preference.latest
                    or time(23, 59)
                )

            if practitioner_id is not None:
                practitioner_ids = [practitioner_id]

            elif treatment_id is not None:
                await cur.execute(
                    """
                    SELECT p.id
                    FROM practitioners p
                    JOIN practitioner_treatments pt
                      ON pt.practitioner_id = p.id
                    WHERE p.clinic_id = %s
                      AND p.active = TRUE
                      AND pt.treatment_id = %s
                    ORDER BY p.full_name
                    """,
                    (
                        clinic_id,
                        treatment_id,
                    ),
                )

                practitioner_ids = [
                    row["id"]
                    for row in await cur.fetchall()
                ]

            else:
                await cur.execute(
                    """
                    SELECT id
                    FROM practitioners
                    WHERE clinic_id = %s
                      AND active = TRUE
                    ORDER BY full_name
                    """,
                    (clinic_id,),
                )

                practitioner_ids = [
                    row["id"]
                    for row in await cur.fetchall()
                ]

            if not practitioner_ids:
                return []

            suggestions: list[
                tuple[UUID, datetime, datetime]
            ] = []

            current_date = start_date

            while current_date <= end_date:
                candidate_start = datetime.combine(
                    current_date,
                    range_start,
                    tzinfo=timezone,
                )

                if (
                    preference is None
                    or preference.exact_time is None
                ):
                    if (
                        candidate_start.minute != 0
                        or candidate_start.second != 0
                        or candidate_start.microsecond != 0
                    ):
                        candidate_start = (
                            candidate_start + timedelta(hours=1)
                        ).replace(
                            minute=0,
                            second=0,
                            microsecond=0,
                        )

                latest_start = datetime.combine(
                    current_date,
                    range_end,
                    tzinfo=timezone,
                )

                if (
                    preference is None
                    or preference.exact_time is None
                ):
                    if candidate_start <= current:
                        elapsed_minutes = (
                            current - candidate_start
                        ).total_seconds() / 60

                        steps_to_skip = int(
                            elapsed_minutes // step_minutes
                        ) + 1

                        candidate_start += timedelta(
                            minutes=(
                                steps_to_skip
                                * step_minutes
                            ),
                        )

                while candidate_start <= latest_start:
                    if candidate_start > current:
                        for candidate_practitioner_id in (
                            practitioner_ids
                        ):
                            try:
                                (
                                    resolved_practitioner,
                                    end_at,
                                ) = await validate_appointment_slot(
                                    cur=cur,
                                    clinic_id=clinic_id,
                                    practitioner_id=(
                                        candidate_practitioner_id
                                    ),
                                    treatment_id=treatment_id,
                                    start_at=candidate_start,
                                    end_at=None,
                                    exclude_appointment_id=(
                                        exclude_appointment_id
                                    ),
                                )
                            except HTTPException:
                                continue

                            if (
                                preference is not None
                                and preference.latest is not None
                                and end_at.astimezone(
                                    timezone
                                ).time()
                                > preference.latest
                            ):
                                continue

                            suggestions.append(
                                (
                                    resolved_practitioner,
                                    candidate_start,
                                    end_at,
                                )
                            )
                            break

                    if len(suggestions) >= limit:
                        return suggestions

                    if (
                        preference is not None
                        and preference.exact_time is not None
                    ):
                        break

                    candidate_start += timedelta(
                        minutes=step_minutes,
                    )

                current_date += timedelta(days=1)

            return suggestions

