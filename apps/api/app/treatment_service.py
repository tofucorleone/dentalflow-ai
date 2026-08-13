from uuid import UUID

from app.db import connection


async def list_active_treatments(
    clinic_id: UUID,
) -> list[dict]:
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
                  AND active = TRUE
                ORDER BY name
                """,
                (clinic_id,),
            )

            return await cur.fetchall()


async def list_treatment_sessions(
    clinic_id: UUID,
    treatment_id: UUID,
) -> list[dict]:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    ts.id,
                    ts.clinic_id,
                    ts.treatment_id,
                    ts.position,
                    ts.name,
                    ts.description,
                    ts.duration_minutes,
                    ts.created_at,
                    ts.updated_at
                FROM treatment_sessions ts
                JOIN treatments t
                  ON t.id = ts.treatment_id
                 AND t.clinic_id = ts.clinic_id
                WHERE ts.clinic_id = %s
                  AND ts.treatment_id = %s
                ORDER BY ts.position, ts.created_at
                """,
                (
                    clinic_id,
                    treatment_id,
                ),
            )

            return await cur.fetchall()


async def create_treatment_session(
    clinic_id: UUID,
    treatment_id: UUID,
    *,
    name: str,
    description: str | None,
    duration_minutes: int,
    position: int | None = None,
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id
                FROM treatments
                WHERE id = %s
                  AND clinic_id = %s
                """,
                (
                    treatment_id,
                    clinic_id,
                ),
            )

            if await cur.fetchone() is None:
                raise ValueError("Soin introuvable.")

            if position is None:
                await cur.execute(
                    """
                    SELECT COALESCE(MAX(position), 0) + 1 AS next_position
                    FROM treatment_sessions
                    WHERE clinic_id = %s
                      AND treatment_id = %s
                    """,
                    (
                        clinic_id,
                        treatment_id,
                    ),
                )

                row = await cur.fetchone()
                position = int(row["next_position"])

            await cur.execute(
                """
                INSERT INTO treatment_sessions (
                    clinic_id,
                    treatment_id,
                    position,
                    name,
                    description,
                    duration_minutes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    clinic_id,
                    treatment_id,
                    position,
                    name,
                    description,
                    duration_minutes,
                ),
            )

            session = await cur.fetchone()
            await conn.commit()

            return session


async def update_treatment_session(
    clinic_id: UUID,
    treatment_id: UUID,
    session_id: UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    duration_minutes: int | None = None,
) -> dict:
    changes = []
    values = []

    if name is not None:
        changes.append("name = %s")
        values.append(name)

    if description is not None:
        changes.append("description = %s")
        values.append(description)

    if duration_minutes is not None:
        changes.append("duration_minutes = %s")
        values.append(duration_minutes)

    if not changes:
        raise ValueError("Aucune modification fournie.")

    changes.append("updated_at = NOW()")

    values.extend(
        [
            clinic_id,
            treatment_id,
            session_id,
        ]
    )

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                UPDATE treatment_sessions
                SET {", ".join(changes)}
                WHERE clinic_id = %s
                  AND treatment_id = %s
                  AND id = %s
                RETURNING *
                """,
                values,
            )

            session = await cur.fetchone()

            if session is None:
                raise ValueError("Séance introuvable.")

            await conn.commit()

            return session


async def delete_treatment_session(
    clinic_id: UUID,
    treatment_id: UUID,
    session_id: UUID,
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM treatment_sessions
                WHERE clinic_id = %s
                  AND treatment_id = %s
                  AND id = %s
                RETURNING *
                """,
                (
                    clinic_id,
                    treatment_id,
                    session_id,
                ),
            )

            session = await cur.fetchone()

            if session is None:
                raise ValueError("Séance introuvable.")

            await cur.execute(
                """
                WITH ordered AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            ORDER BY position, created_at
                        ) AS new_position
                    FROM treatment_sessions
                    WHERE clinic_id = %s
                      AND treatment_id = %s
                )
                UPDATE treatment_sessions ts
                SET
                    position = ordered.new_position,
                    updated_at = NOW()
                FROM ordered
                WHERE ts.id = ordered.id
                """,
                (
                    clinic_id,
                    treatment_id,
                ),
            )

            await conn.commit()

            return session


async def reorder_treatment_sessions(
    clinic_id: UUID,
    treatment_id: UUID,
    session_ids: list[UUID],
) -> list[dict]:
    if not session_ids:
        return []

    if len(session_ids) != len(set(session_ids)):
        raise ValueError(
            "Une séance apparaît plusieurs fois dans le nouvel ordre."
        )

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id
                FROM treatment_sessions
                WHERE clinic_id = %s
                  AND treatment_id = %s
                ORDER BY position
                FOR UPDATE
                """,
                (
                    clinic_id,
                    treatment_id,
                ),
            )

            existing_rows = await cur.fetchall()
            existing_ids = [row["id"] for row in existing_rows]

            if set(existing_ids) != set(session_ids):
                raise ValueError(
                    "La liste doit contenir exactement toutes les séances du soin."
                )

            # Décalage temporaire vers une plage positive libre.
            # On évite ainsi à la fois :
            # - CHECK(position > 0)
            # - UNIQUE(treatment_id, position)
            offset = len(session_ids) + 1000

            await cur.execute(
                """
                UPDATE treatment_sessions
                SET position = position + %s
                WHERE clinic_id = %s
                  AND treatment_id = %s
                """,
                (
                    offset,
                    clinic_id,
                    treatment_id,
                ),
            )

            for index, session_id in enumerate(session_ids, start=1):
                await cur.execute(
                    """
                    UPDATE treatment_sessions
                    SET
                        position = %s,
                        updated_at = NOW()
                    WHERE clinic_id = %s
                      AND treatment_id = %s
                      AND id = %s
                    """,
                    (
                        index,
                        clinic_id,
                        treatment_id,
                        session_id,
                    ),
                )

            await conn.commit()

    return await list_treatment_sessions(
        clinic_id=clinic_id,
        treatment_id=treatment_id,
    )
