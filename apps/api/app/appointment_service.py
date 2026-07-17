from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.google_calendar import (
    CalendarConfigurationError,
    CalendarOperationError,
    create_event,
    delete_event,
    make_event_body,
    update_event,
)
from app.schemas import (
    AppointmentIn,
    AppointmentRescheduleIn,
)


async def clinic_timezone(
    cur,
    clinic_id: UUID,
) -> str:
    await cur.execute(
        "SELECT timezone FROM clinics WHERE id = %s",
        (clinic_id,),
    )
    row = await cur.fetchone()

    return row["timezone"] if row else "Africa/Algiers"


async def treatment_duration(
    cur,
    clinic_id: UUID,
    treatment_id: UUID | None,
) -> int:
    if treatment_id is None:
        return 30

    await cur.execute(
        """
        SELECT duration_minutes
        FROM treatments
        WHERE clinic_id = %s
          AND id = %s
          AND active = TRUE
        """,
        (
            clinic_id,
            treatment_id,
        ),
    )
    row = await cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Soin introuvable.",
        )

    return int(row["duration_minutes"])


async def resolve_practitioner(
    cur,
    clinic_id: UUID,
    practitioner_id: UUID | None,
    treatment_id: UUID | None,
) -> UUID:
    if practitioner_id is not None:
        await cur.execute(
            """
            SELECT id
            FROM practitioners
            WHERE clinic_id = %s
              AND id = %s
              AND active = TRUE
            """,
            (
                clinic_id,
                practitioner_id,
            ),
        )
        row = await cur.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Praticien introuvable.",
            )

        if treatment_id is not None:
            await cur.execute(
                """
                SELECT 1
                FROM practitioner_treatments
                WHERE practitioner_id = %s
                  AND treatment_id = %s
                LIMIT 1
                """,
                (
                    practitioner_id,
                    treatment_id,
                ),
            )

            if await cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Ce praticien ne réalise pas le soin demandé."
                    ),
                )

        return row["id"]

    if treatment_id is not None:
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
            LIMIT 1
            """,
            (
                clinic_id,
                treatment_id,
            ),
        )
        row = await cur.fetchone()

        if row is not None:
            return row["id"]

    await cur.execute(
        """
        SELECT id
        FROM practitioners
        WHERE clinic_id = %s
          AND active = TRUE
        ORDER BY full_name
        LIMIT 1
        """,
        (clinic_id,),
    )
    row = await cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aucun praticien actif n’est configuré.",
        )

    return row["id"]


async def validate_opening_hours(
    cur,
    clinic_id: UUID,
    practitioner_id: UUID,
    start_at: datetime,
    end_at: datetime,
    timezone_name: str,
) -> None:
    timezone = ZoneInfo(timezone_name)
    local_start = start_at.astimezone(timezone)
    local_end = end_at.astimezone(timezone)

    if local_start.date() != local_end.date():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le rendez-vous doit commencer et finir le même jour.",
        )

    weekday = local_start.isoweekday()

    await cur.execute(
        """
        SELECT open_time, close_time, is_closed
        FROM opening_hours
        WHERE clinic_id = %s
          AND day_of_week = %s
          AND practitioner_id = %s
        LIMIT 1
        """,
        (
            clinic_id,
            weekday,
            practitioner_id,
        ),
    )
    opening_hours = await cur.fetchone()

    if opening_hours is None:
        await cur.execute(
            """
            SELECT open_time, close_time, is_closed
            FROM opening_hours
            WHERE clinic_id = %s
              AND day_of_week = %s
              AND practitioner_id IS NULL
            LIMIT 1
            """,
            (
                clinic_id,
                weekday,
            ),
        )
        opening_hours = await cur.fetchone()

    if opening_hours is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aucun horaire n’est configuré pour ce jour.",
        )

    if opening_hours["is_closed"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La clinique est fermée ce jour-là.",
        )

    if (
        local_start.time() < opening_hours["open_time"]
        or local_end.time() > opening_hours["close_time"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Créneau hors horaires. Ouverture : "
                f"{opening_hours['open_time']}–"
                f"{opening_hours['close_time']}."
            ),
        )

    await cur.execute(
        """
        SELECT reason
        FROM holidays
        WHERE clinic_id = %s
          AND (
              practitioner_id IS NULL
              OR practitioner_id = %s
          )
          AND %s BETWEEN start_date AND end_date
        LIMIT 1
        """,
        (
            clinic_id,
            practitioner_id,
            local_start.date(),
        ),
    )
    holiday = await cur.fetchone()

    if holiday is not None:
        reason = holiday["reason"] or "fermeture exceptionnelle"

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Créneau indisponible : {reason}.",
        )


async def validate_no_overlap(
    cur,
    clinic_id: UUID,
    practitioner_id: UUID,
    start_at: datetime,
    end_at: datetime,
    exclude_appointment_id: UUID | None = None,
) -> None:
    await cur.execute(
        """
        SELECT id, start_at, end_at
        FROM appointments
        WHERE clinic_id = %s
          AND practitioner_id = %s
          AND status IN ('pending', 'confirmed')
          AND start_at < %s
          AND end_at > %s
          AND (
              %s::uuid IS NULL
              OR id <> %s::uuid
          )
        LIMIT 1
        """,
        (
            clinic_id,
            practitioner_id,
            end_at,
            start_at,
            exclude_appointment_id,
            exclude_appointment_id,
        ),
    )
    conflicting_appointment = await cur.fetchone()

    if conflicting_appointment is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Ce créneau est déjà occupé.",
                "conflicting_appointment_id": str(
                    conflicting_appointment["id"],
                ),
                "conflicting_start_at": conflicting_appointment[
                    "start_at"
                ].isoformat(),
                "conflicting_end_at": conflicting_appointment[
                    "end_at"
                ].isoformat(),
            },
        )


async def validate_appointment_slot(
    cur,
    clinic_id: UUID,
    practitioner_id: UUID | None,
    treatment_id: UUID | None,
    start_at: datetime,
    end_at: datetime | None,
    exclude_appointment_id: UUID | None = None,
) -> tuple[UUID, datetime]:
    duration_minutes = await treatment_duration(
        cur,
        clinic_id,
        treatment_id,
    )

    resolved_end = end_at or (
        start_at + timedelta(minutes=duration_minutes)
    )

    resolved_practitioner = await resolve_practitioner(
        cur,
        clinic_id,
        practitioner_id,
        treatment_id,
    )

    timezone_name = await clinic_timezone(
        cur,
        clinic_id,
    )

    await validate_opening_hours(
        cur,
        clinic_id,
        resolved_practitioner,
        start_at,
        resolved_end,
        timezone_name,
    )

    await validate_no_overlap(
        cur,
        clinic_id,
        resolved_practitioner,
        start_at,
        resolved_end,
        exclude_appointment_id,
    )

    return resolved_practitioner, resolved_end


async def create_appointment_record(
    cur,
    conn,
    clinic_id: UUID,
    payload: AppointmentIn,
) -> dict:
    await cur.execute(
        """
        SELECT id, full_name, phone
        FROM patients
        WHERE clinic_id = %s
          AND id = %s
          AND active = TRUE
        """,
        (
            clinic_id,
            payload.patient_id,
        ),
    )

    patient = await cur.fetchone()

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient introuvable.",
        )

    practitioner_id, end_at = await validate_appointment_slot(
        cur=cur,
        clinic_id=clinic_id,
        practitioner_id=payload.practitioner_id,
        treatment_id=payload.treatment_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
    )

    await cur.execute(
        """
        SELECT
            p.full_name AS practitioner_name,
            COALESCE(
                p.google_calendar_id,
                c.google_calendar_id
            ) AS calendar_id,
            c.timezone,
            t.name AS treatment_name
        FROM practitioners p
        JOIN clinics c
          ON c.id = p.clinic_id
        LEFT JOIN treatments t
          ON t.id = %s
         AND t.clinic_id = c.id
        WHERE p.id = %s
          AND p.clinic_id = %s
        """,
        (
            payload.treatment_id,
            practitioner_id,
            clinic_id,
        ),
    )

    appointment_context = await cur.fetchone()

    if (
        appointment_context is None
        or not appointment_context["calendar_id"]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Aucun calendrier Google n’est configuré "
                "pour ce praticien ou cette clinique."
            ),
        )

    await cur.execute(
        """
        INSERT INTO appointments (
            clinic_id,
            patient_id,
            practitioner_id,
            treatment_id,
            channel,
            status,
            start_at,
            end_at,
            notes
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            'pending',
            %s,
            %s,
            %s
        )
        RETURNING *
        """,
        (
            clinic_id,
            payload.patient_id,
            practitioner_id,
            payload.treatment_id,
            payload.channel,
            payload.start_at,
            end_at,
            payload.notes,
        ),
    )

    appointment = await cur.fetchone()

    event_body = make_event_body(
        patient_name=patient["full_name"],
        patient_phone=patient["phone"],
        treatment_name=appointment_context["treatment_name"],
        practitioner_name=appointment_context["practitioner_name"],
        start_at=payload.start_at,
        end_at=end_at,
        timezone_name=appointment_context["timezone"],
        appointment_id=str(appointment["id"]),
    )

    try:
        event = await create_event(
            appointment_context["calendar_id"],
            event_body,
        )
    except (
        CalendarConfigurationError,
        CalendarOperationError,
    ) as exc:
        await conn.rollback()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    await cur.execute(
        """
        UPDATE appointments
        SET
            status = %s,
            google_calendar_event_id = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (
            payload.status,
            event["id"],
            appointment["id"],
        ),
    )

    result = await cur.fetchone()
    await conn.commit()

    return {
        **result,
        "google_calendar_html_link": event.get("htmlLink"),
    }


async def cancel_appointment_record(
    cur,
    conn,
    clinic_id: UUID,
    appointment_id: UUID,
) -> dict:
    await cur.execute(
        """
        SELECT
            a.id,
            a.status,
            a.google_calendar_event_id,
            COALESCE(
                pr.google_calendar_id,
                c.google_calendar_id
            ) AS calendar_id
        FROM appointments a
        LEFT JOIN practitioners pr
          ON pr.id = a.practitioner_id
        JOIN clinics c
          ON c.id = a.clinic_id
        WHERE a.id = %s
          AND a.clinic_id = %s
        FOR UPDATE OF a
        """,
        (
            appointment_id,
            clinic_id,
        ),
    )

    appointment = await cur.fetchone()

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rendez-vous introuvable.",
        )

    if appointment["status"] == "cancelled":
        return {
            "id": appointment_id,
            "status": "cancelled",
            "already_cancelled": True,
        }

    if (
        appointment["google_calendar_event_id"]
        and appointment["calendar_id"]
    ):
        try:
            await delete_event(
                appointment["calendar_id"],
                appointment["google_calendar_event_id"],
            )
        except (
            CalendarConfigurationError,
            CalendarOperationError,
        ) as exc:
            await conn.rollback()

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    await cur.execute(
        """
        UPDATE appointments
        SET
            status = 'cancelled',
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (appointment_id,),
    )

    result = await cur.fetchone()
    await conn.commit()

    return result



async def get_next_patient_appointment(
    clinic_id: UUID,
    patient_id: UUID,
) -> dict | None:
    from app.db import connection

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    a.id,
                    a.status,
                    a.start_at,
                    a.end_at,
                    a.practitioner_id,
                    a.treatment_id,
                    pr.full_name AS practitioner_name,
                    t.name AS treatment_name
                FROM appointments a
                LEFT JOIN practitioners pr
                  ON pr.id = a.practitioner_id
                LEFT JOIN treatments t
                  ON t.id = a.treatment_id
                WHERE a.clinic_id = %s
                  AND a.patient_id = %s
                  AND a.status IN ('pending', 'confirmed')
                  AND a.start_at >= NOW()
                ORDER BY a.start_at
                LIMIT 1
                """,
                (
                    clinic_id,
                    patient_id,
                ),
            )

            return await cur.fetchone()


async def reschedule_appointment_record(
    cur,
    conn,
    clinic_id: UUID,
    appointment_id: UUID,
    payload: AppointmentRescheduleIn,
) -> dict:
    await cur.execute(
        """
        SELECT
            a.*,
            p.full_name AS patient_name,
            p.phone AS patient_phone,
            pr.full_name AS practitioner_name,
            COALESCE(
                pr.google_calendar_id,
                c.google_calendar_id
            ) AS calendar_id,
            c.timezone,
            t.name AS treatment_name
        FROM appointments a
        JOIN patients p
          ON p.id = a.patient_id
        JOIN practitioners pr
          ON pr.id = a.practitioner_id
        JOIN clinics c
          ON c.id = a.clinic_id
        LEFT JOIN treatments t
          ON t.id = a.treatment_id
        WHERE a.id = %s
          AND a.clinic_id = %s
          AND a.status IN ('pending', 'confirmed')
        FOR UPDATE OF a
        """,
        (
            appointment_id,
            clinic_id,
        ),
    )

    appointment = await cur.fetchone()

    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rendez-vous actif introuvable.",
        )

    _, end_at = await validate_appointment_slot(
        cur=cur,
        clinic_id=clinic_id,
        practitioner_id=appointment["practitioner_id"],
        treatment_id=appointment["treatment_id"],
        start_at=payload.start_at,
        end_at=payload.end_at,
        exclude_appointment_id=appointment_id,
    )

    if not appointment["calendar_id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Aucun calendrier Google n’est configuré "
                "pour ce praticien ou cette clinique."
            ),
        )

    event_body = make_event_body(
        patient_name=appointment["patient_name"],
        patient_phone=appointment["patient_phone"],
        treatment_name=appointment["treatment_name"],
        practitioner_name=appointment["practitioner_name"],
        start_at=payload.start_at,
        end_at=end_at,
        timezone_name=appointment["timezone"],
        appointment_id=str(appointment_id),
    )

    try:
        if appointment["google_calendar_event_id"]:
            event = await update_event(
                appointment["calendar_id"],
                appointment["google_calendar_event_id"],
                event_body,
            )
            google_event_id = appointment[
                "google_calendar_event_id"
            ]
        else:
            event = await create_event(
                appointment["calendar_id"],
                event_body,
            )
            google_event_id = event["id"]
    except (
        CalendarConfigurationError,
        CalendarOperationError,
    ) as exc:
        await conn.rollback()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    await cur.execute(
        """
        UPDATE appointments
        SET
            start_at = %s,
            end_at = %s,
            google_calendar_event_id = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (
            payload.start_at,
            end_at,
            google_event_id,
            appointment_id,
        ),
    )

    result = await cur.fetchone()
    await conn.commit()

    return {
        **result,
        "google_calendar_html_link": event.get("htmlLink"),
    }
