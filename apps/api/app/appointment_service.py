from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.copilot.audit import record_copilot_audit_event
from app.conversations.realtime import publish_conversation_event
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
    treatment_session_id: UUID | None = None,
) -> int:
    if treatment_id is None:
        return 30

    # Si le rendez-vous est déjà rattaché à une séance précise,
    # sa durée doit rester celle de cette séance.
    if treatment_session_id is not None:
        await cur.execute(
            """
            SELECT duration_minutes
            FROM treatment_sessions
            WHERE id = %s
              AND clinic_id = %s
              AND treatment_id = %s
            """,
            (
                treatment_session_id,
                clinic_id,
                treatment_id,
            ),
        )

        session = await cur.fetchone()

        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Séance de soin introuvable.",
            )

        return int(session["duration_minutes"])

    # Si le soin est composé mais que la séance n'est pas encore
    # explicitement connue, on utilise sa première séance.
    await cur.execute(
        """
        SELECT duration_minutes
        FROM treatment_sessions
        WHERE clinic_id = %s
          AND treatment_id = %s
        ORDER BY position
        LIMIT 1
        """,
        (
            clinic_id,
            treatment_id,
        ),
    )

    first_session = await cur.fetchone()

    if first_session is not None:
        return int(first_session["duration_minutes"])

    # Soin simple : comportement historique inchangé.
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

    treatment = await cur.fetchone()

    if treatment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Soin introuvable.",
        )

    return int(treatment["duration_minutes"])


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
    treatment_session_id: UUID | None = None,
) -> tuple[UUID, datetime]:
    if (
        start_at.minute != 0
        or start_at.second != 0
        or start_at.microsecond != 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Les rendez-vous doivent commencer à une heure pile "
                "(par exemple 09:00, 10:00 ou 14:00)."
            ),
        )

    duration_minutes = await treatment_duration(
        cur,
        clinic_id,
        treatment_id,
        treatment_session_id,
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

    treatment_session_id = None

    if payload.treatment_id is not None:
        # Vérifier d'abord si ce soin possède un protocole composé.
        await cur.execute(
            """
            SELECT COUNT(*) AS session_count
            FROM treatment_sessions
            WHERE clinic_id = %s
              AND treatment_id = %s
            """,
            (
                clinic_id,
                payload.treatment_id,
            ),
        )

        session_count_row = await cur.fetchone()
        session_count = int(session_count_row["session_count"])

        if session_count > 0:
            # Dernière position effectivement terminée par ce patient
            # pour ce soin.
            await cur.execute(
                """
                SELECT COALESCE(MAX(ts.position), 0) AS completed_position
                FROM appointments a
                JOIN treatment_sessions ts
                  ON ts.id = a.treatment_session_id
                 AND ts.clinic_id = a.clinic_id
                 AND ts.treatment_id = a.treatment_id
                WHERE a.clinic_id = %s
                  AND a.patient_id = %s
                  AND a.treatment_id = %s
                  AND a.status = 'completed'
                """,
                (
                    clinic_id,
                    payload.patient_id,
                    payload.treatment_id,
                ),
            )

            progress_row = await cur.fetchone()
            completed_position = int(
                progress_row["completed_position"]
            )

            # Prendre automatiquement la séance suivante.
            await cur.execute(
                """
                SELECT
                    id,
                    position,
                    name,
                    duration_minutes
                FROM treatment_sessions
                WHERE clinic_id = %s
                  AND treatment_id = %s
                  AND position > %s
                ORDER BY position
                LIMIT 1
                """,
                (
                    clinic_id,
                    payload.treatment_id,
                    completed_position,
                ),
            )

            next_treatment_session = await cur.fetchone()

            if next_treatment_session is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Toutes les séances de ce soin sont déjà "
                        "terminées pour ce patient."
                    ),
                )

            treatment_session_id = next_treatment_session["id"]

            # Éviter de créer deux rendez-vous actifs pour la même
            # séance du protocole.
            await cur.execute(
                """
                SELECT id
                FROM appointments
                WHERE clinic_id = %s
                  AND patient_id = %s
                  AND treatment_id = %s
                  AND treatment_session_id = %s
                  AND status IN ('pending', 'confirmed')
                LIMIT 1
                """,
                (
                    clinic_id,
                    payload.patient_id,
                    payload.treatment_id,
                    treatment_session_id,
                ),
            )

            active_session_appointment = await cur.fetchone()

            if active_session_appointment is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cette séance possède déjà un rendez-vous actif "
                        "pour ce patient."
                    ),
                )

    practitioner_id, end_at = await validate_appointment_slot(
        cur=cur,
        clinic_id=clinic_id,
        practitioner_id=payload.practitioner_id,
        treatment_id=payload.treatment_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        treatment_session_id=treatment_session_id,
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
            treatment_session_id,
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
            treatment_session_id,
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
    await record_copilot_audit_event(
        cur=cur, clinic_id=clinic_id, patient_id=payload.patient_id, action_type="appointment_created", result="success",
        entity_type="appointment", entity_id=result["id"],
        after_data={"start_at": result.get("start_at"), "end_at": result.get("end_at"), "status": result.get("status")},
        metadata={"actor_label": "Équipe clinique", "source": "appointment_service"},
    )
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
            a.patient_id,
            a.practitioner_id,
            a.treatment_id,
            a.start_at,
            a.end_at,
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
    await record_copilot_audit_event(
        cur=cur, clinic_id=clinic_id, patient_id=appointment.get("patient_id"), action_type="appointment_cancelled", result="success",
        entity_type="appointment", entity_id=appointment_id,
        before_data={"start_at": appointment.get("start_at"), "end_at": appointment.get("end_at"), "status": appointment.get("status")},
        after_data={"status": "cancelled"}, metadata={"actor_label": "Équipe clinique", "source": "appointment_service"},
    )
    await conn.commit()

    await publish_conversation_event(
        clinic_id=clinic_id,
        event_type="copilot.task.created",
        data={
            "source": "appointment_cancelled",
            "appointment_id": str(appointment_id),
            "patient_id": (
                str(appointment["patient_id"])
                if appointment.get("patient_id")
                else None
            ),
            "start_at": result.get("start_at"),
            "status": "cancelled",
        },
    )

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
        treatment_session_id=appointment["treatment_session_id"],
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
    await record_copilot_audit_event(
        cur=cur, clinic_id=clinic_id, patient_id=appointment.get("patient_id"), action_type="appointment_rescheduled", result="success",
        entity_type="appointment", entity_id=appointment_id,
        before_data={"start_at": appointment.get("start_at"), "end_at": appointment.get("end_at"), "status": appointment.get("status")},
        after_data={"start_at": result.get("start_at"), "end_at": result.get("end_at"), "status": result.get("status")},
        metadata={"actor_label": "Équipe clinique", "source": "appointment_service"},
    )
    await conn.commit()

    return {
        **result,
        "google_calendar_html_link": event.get("htmlLink"),
    }


async def list_appointments_for_period(
    cur,
    clinic_id: UUID,
    date_from: datetime,
    date_to: datetime,
    limit: int = 100,
) -> list[dict]:
    safe_limit = min(max(limit, 1), 500)

    await cur.execute(
        """
        SELECT
            a.id,
            a.clinic_id,
            a.patient_id,
            a.practitioner_id,
            a.treatment_id,
            a.channel,
            a.status,
            a.start_at,
            a.end_at,
            a.google_calendar_event_id,
            a.notes,
            a.created_at,
            a.updated_at,
            p.full_name AS patient_name,
            p.phone AS patient_phone,
            pr.full_name AS practitioner_name,
            t.name AS treatment_name
        FROM appointments a
        JOIN patients p
          ON p.id = a.patient_id
         AND p.clinic_id = a.clinic_id
        LEFT JOIN practitioners pr
          ON pr.id = a.practitioner_id
         AND pr.clinic_id = a.clinic_id
        LEFT JOIN treatments t
          ON t.id = a.treatment_id
         AND t.clinic_id = a.clinic_id
        WHERE a.clinic_id = %s
          AND a.start_at >= %s
          AND a.start_at < %s
        ORDER BY a.start_at
        LIMIT %s
        """,
        (
            clinic_id,
            date_from,
            date_to,
            safe_limit,
        ),
    )

    return await cur.fetchall()


async def mark_appointment_no_show(
    *,
    cur,
    conn,
    clinic_id: UUID,
    appointment_id: UUID,
) -> dict:
    await cur.execute(
        """
        SELECT
            id,
            patient_id,
            status,
            start_at,
            end_at
        FROM appointments
        WHERE id = %s
          AND clinic_id = %s
        FOR UPDATE
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

    if appointment["status"] == "no_show":
        return appointment

    await cur.execute(
        """
        UPDATE appointments
        SET
            status = 'no_show',
            updated_at = NOW()
        WHERE id = %s
          AND clinic_id = %s
        RETURNING *
        """,
        (
            appointment_id,
            clinic_id,
        ),
    )

    result = await cur.fetchone()

    await record_copilot_audit_event(
        cur=cur,
        clinic_id=clinic_id,
        patient_id=appointment.get("patient_id"),
        action_type="appointment_no_show",
        result="success",
        entity_type="appointment",
        entity_id=appointment_id,
        before_data={
            "status": appointment.get("status"),
            "start_at": appointment.get("start_at"),
            "end_at": appointment.get("end_at"),
        },
        after_data={
            "status": "no_show",
        },
        metadata={
            "actor_label": "Équipe clinique",
            "source": "appointment_service",
        },
    )

    await conn.commit()

    await publish_conversation_event(
        clinic_id=clinic_id,
        event_type="copilot.task.created",
        data={
            "source": "appointment_no_show",
            "appointment_id": str(appointment_id),
            "patient_id": (
                str(appointment["patient_id"])
                if appointment.get("patient_id")
                else None
            ),
            "status": "no_show",
        },
    )

    return result


async def mark_appointment_completed(
    *,
    cur,
    conn,
    clinic_id: UUID,
    appointment_id: UUID,
) -> dict:
    await cur.execute(
        """
        SELECT
            id,
            patient_id,
            treatment_id,
            treatment_session_id,
            status,
            start_at,
            end_at
        FROM appointments
        WHERE id = %s
          AND clinic_id = %s
        FOR UPDATE
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

    if appointment["status"] == "completed":
        return appointment

    if appointment["status"] not in {"pending", "confirmed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Seul un rendez-vous actif peut être marqué comme terminé."
            ),
        )

    await cur.execute(
        """
        UPDATE appointments
        SET
            status = 'completed',
            updated_at = NOW()
        WHERE id = %s
          AND clinic_id = %s
        RETURNING *
        """,
        (
            appointment_id,
            clinic_id,
        ),
    )

    result = await cur.fetchone()

    await record_copilot_audit_event(
        cur=cur,
        clinic_id=clinic_id,
        patient_id=appointment.get("patient_id"),
        action_type="appointment_completed",
        result="success",
        entity_type="appointment",
        entity_id=appointment_id,
        before_data={
            "status": appointment.get("status"),
            "start_at": appointment.get("start_at"),
            "end_at": appointment.get("end_at"),
            "treatment_id": appointment.get("treatment_id"),
            "treatment_session_id": appointment.get(
                "treatment_session_id"
            ),
        },
        after_data={
            "status": "completed",
        },
        metadata={
            "actor_label": "Équipe clinique",
            "source": "appointment_service",
        },
    )

    await conn.commit()

    await publish_conversation_event(
        clinic_id=clinic_id,
        event_type="appointment.completed",
        data={
            "appointment_id": str(appointment_id),
            "patient_id": (
                str(appointment["patient_id"])
                if appointment.get("patient_id")
                else None
            ),
            "treatment_id": (
                str(appointment["treatment_id"])
                if appointment.get("treatment_id")
                else None
            ),
            "treatment_session_id": (
                str(appointment["treatment_session_id"])
                if appointment.get("treatment_session_id")
                else None
            ),
            "status": "completed",
        },
    )

    return result


async def mark_appointment_confirmed(
    *,
    cur,
    conn,
    clinic_id: UUID,
    appointment_id: UUID,
) -> dict:
    await cur.execute(
        """
        SELECT
            id,
            patient_id,
            status,
            start_at,
            end_at
        FROM appointments
        WHERE id = %s
          AND clinic_id = %s
        FOR UPDATE
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

    if appointment["status"] == "confirmed":
        return appointment

    if appointment["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Seul un rendez-vous en attente peut être confirmé."
            ),
        )

    await cur.execute(
        """
        UPDATE appointments
        SET
            status = 'confirmed',
            updated_at = NOW()
        WHERE id = %s
          AND clinic_id = %s
        RETURNING *
        """,
        (
            appointment_id,
            clinic_id,
        ),
    )

    result = await cur.fetchone()

    await record_copilot_audit_event(
        cur=cur,
        clinic_id=clinic_id,
        patient_id=appointment.get("patient_id"),
        action_type="appointment_confirmed",
        result="success",
        entity_type="appointment",
        entity_id=appointment_id,
        before_data={
            "status": appointment.get("status"),
            "start_at": appointment.get("start_at"),
            "end_at": appointment.get("end_at"),
        },
        after_data={
            "status": "confirmed",
        },
        metadata={
            "actor_label": "Patient",
            "source": "appointment_service",
        },
    )

    await conn.commit()

    await publish_conversation_event(
        clinic_id=clinic_id,
        event_type="appointment.confirmed",
        data={
            "appointment_id": str(appointment_id),
            "patient_id": (
                str(appointment["patient_id"])
                if appointment.get("patient_id")
                else None
            ),
            "status": "confirmed",
        },
    )

    return result
