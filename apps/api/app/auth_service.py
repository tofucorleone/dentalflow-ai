from uuid import UUID

from fastapi import HTTPException, status

from app.auth_schemas import UserCreate
from app.db import connection
from app.security import hash_password, verify_password


async def get_user_by_email(email: str) -> dict | None:
    normalized_email = email.strip().lower()

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    clinic_id,
                    email,
                    password_hash,
                    full_name,
                    role,
                    job_title,
                    phone,
                    active,
                    must_change_password,
                    created_at,
                    updated_at
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (normalized_email,),
            )

            return await cur.fetchone()


async def get_user_by_id(user_id: UUID) -> dict | None:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    clinic_id,
                    email,
                    password_hash,
                    full_name,
                    role,
                    job_title,
                    phone,
                    active,
                    must_change_password,
                    created_at,
                    updated_at
                FROM users
                WHERE id = %s
                LIMIT 1
                """,
                (user_id,),
            )

            return await cur.fetchone()


async def create_user(payload: UserCreate) -> dict:
    normalized_email = payload.email.strip().lower()

    existing_user = await get_user_by_email(normalized_email)

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un utilisateur existe déjà avec cette adresse e-mail.",
        )

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id
                FROM clinics
                WHERE id = %s
                LIMIT 1
                """,
                (payload.clinic_id,),
            )

            clinic = await cur.fetchone()

            if clinic is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Clinique introuvable.",
                )

            password_digest = hash_password(payload.password)

            await cur.execute(
                """
                INSERT INTO users (
                    clinic_id,
                    email,
                    password_hash,
                    full_name,
                    role,
                    job_title,
                    phone
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    clinic_id,
                    email,
                    full_name,
                    role,
                    job_title,
                    phone,
                    active,
                    must_change_password,
                    created_at,
                    updated_at
                """,
                (
                    payload.clinic_id,
                    normalized_email,
                    password_digest,
                    payload.full_name,
                    payload.role,
                    payload.job_title,
                    payload.phone,
                ),
            )

            user = await cur.fetchone()
            await conn.commit()

            return user


async def authenticate_user(email: str, password: str) -> dict | None:
    user = await get_user_by_email(email)

    if user is None:
        return None

    if not user["active"]:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE users
                SET last_login_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (user["id"],),
            )
            await conn.commit()

    return user

