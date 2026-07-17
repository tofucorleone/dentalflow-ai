from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from app.appointment_service import (
    cancel_appointment_record,
    create_appointment_record,
    reschedule_appointment_record,
    validate_appointment_slot,
)
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import UniqueViolation

from app.db import connection
from app.google_calendar import (
    CalendarConfigurationError,
    CalendarOperationError,
    create_event,
    delete_event,
    make_event_body,
    update_event,
)
from app.deps import clinic_id
from app.practitioner_service import (
    list_practitioners as list_practitioners_service,
)
from app.treatment_service import list_active_treatments
from app.schemas import (
    AppointmentIn,
    AppointmentRescheduleIn,
    AvailabilityIn,
    PatientIn,
    PatientPatch,
    PractitionerIn,
    TreatmentIn,
    TreatmentPatch,
    

)


router = APIRouter()


@router.get("/clinics", tags=["Cliniques"])
async def list_clinics() -> list[dict]:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, name, slug, timezone, language, active, created_at
                FROM clinics
                ORDER BY name
                """
            )
            return await cur.fetchall()


@router.get("/treatments", tags=["Soins"])
async def list_treatments(
    current_clinic: UUID = Depends(clinic_id),
    include_inactive: bool = False,
) -> list[dict]:
    if not include_inactive:
        return await list_active_treatments(current_clinic)

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    clinic_id,
                    name,
                    description,
                    duration_minutes,
                    price,
                    requires_consultation,
                    active,
                    created_at,
                    updated_at
                FROM treatments
                WHERE clinic_id = %s
                ORDER BY name
                """,
                (current_clinic,),
            )

            return await cur.fetchall()


@router.post("/treatments", tags=["Soins"], status_code=status.HTTP_201_CREATED)
async def create_treatment(
    payload: TreatmentIn,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    try:
        async with connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO treatments (
                        clinic_id, name, description, duration_minutes,
                        price, requires_consultation, active
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        current_clinic,
                        payload.name,
                        payload.description,
                        payload.duration_minutes,
                        payload.price,
                        payload.requires_consultation,
                        payload.active,
                    ),
                )
                row = await cur.fetchone()
                await conn.commit()
                return row
    except UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un soin avec ce nom existe déjà.",
        ) from exc


@router.patch("/treatments/{treatment_id}", tags=["Soins"])
async def patch_treatment(
    treatment_id: UUID,
    payload: TreatmentPatch,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune modification fournie.",
        )

    allowed = {
        "name",
        "description",
        "duration_minutes",
        "price",
        "requires_consultation",
        "active",
    }

    sets = []
    values = []
    for key, value in changes.items():
        if key in allowed:
            sets.append(f"{key} = %s")
            values.append(value)

    sets.append("updated_at = NOW()")
    values.extend([current_clinic, treatment_id])

    query = f"""
        UPDATE treatments
        SET {", ".join(sets)}
        WHERE clinic_id = %s AND id = %s
        RETURNING *
    """

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, values)
            row = await cur.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Soin introuvable.",
                )
            await conn.commit()
            return row


@router.get("/practitioners", tags=["Praticiens"])
async def list_practitioners(
    current_clinic: UUID = Depends(clinic_id),
    include_inactive: bool = False,
) -> list[dict]:
    return await list_practitioners_service(
        clinic_id=current_clinic,
        include_inactive=include_inactive,
    )


@router.post("/practitioners", tags=["Praticiens"], status_code=status.HTTP_201_CREATED)
async def create_practitioner(
    payload: PractitionerIn,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO practitioners (
                    clinic_id, full_name, speciality, google_calendar_id,
                    phone, email, active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    current_clinic,
                    payload.full_name,
                    payload.speciality,
                    payload.google_calendar_id,
                    payload.phone,
                    payload.email,
                    payload.active,
                ),
            )
            row = await cur.fetchone()
            await conn.commit()
            return row


@router.get("/patients", tags=["Patients"])
async def list_patients(
    current_clinic: UUID = Depends(clinic_id),
    limit: int = 50,
) -> list[dict]:
    limit = min(max(limit, 1), 200)
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, clinic_id, phone, full_name, email,
                       administrative_notes, active, created_at, updated_at
                FROM patients
                WHERE clinic_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (current_clinic, limit),
            )
            return await cur.fetchall()


@router.post("/patients", tags=["Patients"], status_code=status.HTTP_201_CREATED)
async def upsert_patient(
    payload: PatientIn,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO patients (
                    clinic_id, phone, full_name, email, administrative_notes
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (clinic_id, phone)
                DO UPDATE SET
                    full_name = COALESCE(EXCLUDED.full_name, patients.full_name),
                    email = COALESCE(EXCLUDED.email, patients.email),
                    administrative_notes = COALESCE(
                        EXCLUDED.administrative_notes,
                        patients.administrative_notes
                    ),
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    current_clinic,
                    payload.phone,
                    payload.full_name,
                    payload.email,
                    payload.administrative_notes,
                ),
            )
            row = await cur.fetchone()
            await conn.commit()
            return row


@router.patch("/patients/{patient_id}", tags=["Patients"])
async def update_patient(
    patient_id: UUID,
    payload: PatientPatch,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune modification fournie.",
        )

    allowed_fields = {
        "phone",
        "full_name",
        "email",
        "administrative_notes",
    }

    fields = []
    values = []

    for field, value in updates.items():
        if field not in allowed_fields:
            continue

        fields.append(f"{field} = %s")
        values.append(value)

    fields.append("updated_at = NOW()")

    values.extend(
        [
            patient_id,
            current_clinic,
        ]
    )

    query = f"""
        UPDATE patients
        SET {", ".join(fields)}
        WHERE id = %s
          AND clinic_id = %s
        RETURNING
            id,
            clinic_id,
            phone,
            full_name,
            email,
            administrative_notes,
            active,
            created_at,
            updated_at
    """

    try:
        async with connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, values)
                patient = await cur.fetchone()

                if patient is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Patient introuvable.",
                    )

                await conn.commit()
                return patient

    except UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce numéro de téléphone est déjà utilisé.",
        ) from exc


async def _clinic_timezone(cur, current_clinic: UUID) -> str:
    await cur.execute(
        "SELECT timezone FROM clinics WHERE id = %s",
        (current_clinic,),
    )
    row = await cur.fetchone()
    return row["timezone"] if row else "Africa/Algiers"


async def _duration(cur, current_clinic: UUID, treatment_id: UUID | None) -> int:
    if treatment_id is None:
        return 30

    await cur.execute(
        """
        SELECT duration_minutes
        FROM treatments
        WHERE clinic_id = %s AND id = %s AND active = TRUE
        """,
        (current_clinic, treatment_id),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Soin introuvable.",
        )
    return int(row["duration_minutes"])


async def _practitioner(
    cur,
    current_clinic: UUID,
    practitioner_id: UUID | None,
    treatment_id: UUID | None,
) -> UUID:
    if practitioner_id is not None:
        await cur.execute(
            """
            SELECT id
            FROM practitioners
            WHERE clinic_id = %s AND id = %s AND active = TRUE
            """,
            (current_clinic, practitioner_id),
        )
        row = await cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Praticien introuvable.",
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
            (current_clinic, treatment_id),
        )
        row = await cur.fetchone()
        if row is not None:
            return row["id"]

    await cur.execute(
        """
        SELECT id
        FROM practitioners
        WHERE clinic_id = %s AND active = TRUE
        ORDER BY full_name
        LIMIT 1
        """,
        (current_clinic,),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aucun praticien actif n’est configuré.",
        )
    return row["id"]


async def _hours_and_holidays(
    cur,
    current_clinic: UUID,
    practitioner_id: UUID,
    start_at: datetime,
    end_at: datetime,
    timezone_name: str,
) -> None:
    tz = ZoneInfo(timezone_name)
    local_start = start_at.astimezone(tz)
    local_end = end_at.astimezone(tz)

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
        (current_clinic, weekday, practitioner_id),
    )
    row = await cur.fetchone()

    if row is None:
        await cur.execute(
            """
            SELECT open_time, close_time, is_closed
            FROM opening_hours
            WHERE clinic_id = %s
              AND day_of_week = %s
              AND practitioner_id IS NULL
            LIMIT 1
            """,
            (current_clinic, weekday),
        )
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aucun horaire n’est configuré pour ce jour.",
        )

    if row["is_closed"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La clinique est fermée ce jour-là.",
        )

    if local_start.time() < row["open_time"] or local_end.time() > row["close_time"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Créneau hors horaires. Ouverture : "
                f"{row['open_time']}–{row['close_time']}."
            ),
        )

    await cur.execute(
        """
        SELECT reason
        FROM holidays
        WHERE clinic_id = %s
          AND (practitioner_id IS NULL OR practitioner_id = %s)
          AND %s BETWEEN start_date AND end_date
        LIMIT 1
        """,
        (current_clinic, practitioner_id, local_start.date()),
    )
    holiday = await cur.fetchone()
    if holiday is not None:
        reason = holiday["reason"] or "fermeture exceptionnelle"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Créneau indisponible : {reason}.",
        )


async def _overlap(
    cur,
    current_clinic: UUID,
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
          AND (%s::uuid IS NULL OR id <> %s::uuid)
        LIMIT 1
        """,
        (
            current_clinic,
            practitioner_id,
            end_at,
            start_at,
            exclude_appointment_id,
            exclude_appointment_id,
        ),
    )
    row = await cur.fetchone()
    if row is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Ce créneau est déjà occupé.",
                "conflicting_appointment_id": str(row["id"]),
                "conflicting_start_at": row["start_at"].isoformat(),
                "conflicting_end_at": row["end_at"].isoformat(),
            },
        )


async def _validate_slot(
    cur,
    current_clinic: UUID,
    practitioner_id: UUID | None,
    treatment_id: UUID | None,
    start_at: datetime,
    end_at: datetime | None,
    exclude_appointment_id: UUID | None = None,
) -> tuple[UUID, datetime]:
    return await validate_appointment_slot(
        cur=cur,
        clinic_id=current_clinic,
        practitioner_id=practitioner_id,
        treatment_id=treatment_id,
        start_at=start_at,
        end_at=end_at,
        exclude_appointment_id=exclude_appointment_id,
    )


@router.get("/appointments", tags=["Rendez-vous"])
async def list_appointments(
    current_clinic: UUID = Depends(clinic_id),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
) -> list[dict]:
    limit = min(max(limit, 1), 500)

    query = """
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
        JOIN patients p ON p.id = a.patient_id
        LEFT JOIN practitioners pr ON pr.id = a.practitioner_id
        LEFT JOIN treatments t ON t.id = a.treatment_id
        WHERE a.clinic_id = %s
    """
    params: list = [current_clinic]

    if date_from is not None:
        query += " AND a.start_at >= %s"
        params.append(date_from)
    if date_to is not None:
        query += " AND a.start_at < %s"
        params.append(date_to)

    query += " ORDER BY a.start_at LIMIT %s"
    params.append(limit)

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchall()


@router.post("/appointments/availability", tags=["Rendez-vous"])
async def availability(
    payload: AvailabilityIn,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            practitioner_id, end_at = await _validate_slot(
                cur,
                current_clinic,
                payload.practitioner_id,
                payload.treatment_id,
                payload.start_at,
                payload.end_at,
            )
            return {
                "available": True,
                "practitioner_id": practitioner_id,
                "start_at": payload.start_at,
                "end_at": end_at,
            }


@router.post(
    "/appointments",
    tags=["Rendez-vous"],
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment(
    payload: AppointmentIn,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            return await create_appointment_record(
                cur=cur,
                conn=conn,
                clinic_id=current_clinic,
                payload=payload,
            )


@router.patch(
    "/appointments/{appointment_id}/reschedule",
    tags=["Rendez-vous"],
)
async def reschedule_appointment(
    appointment_id: UUID,
    payload: AppointmentRescheduleIn,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            return await reschedule_appointment_record(
                cur=cur,
                conn=conn,
                clinic_id=current_clinic,
                appointment_id=appointment_id,
                payload=payload,
            )


@router.delete(
    "/appointments/{appointment_id}",
    tags=["Rendez-vous"],
)
async def cancel_appointment(
    appointment_id: UUID,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            return await cancel_appointment_record(
                cur=cur,
                conn=conn,
                clinic_id=current_clinic,
                appointment_id=appointment_id,
            )

