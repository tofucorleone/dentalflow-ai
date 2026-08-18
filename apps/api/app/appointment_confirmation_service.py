from datetime import datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from app.ai.conversation_message import (
    create_conversation_message,
    update_conversation_message_status,
)
from app.ai.conversation_thread import (
    get_or_create_conversation_thread,
    update_conversation_thread_after_message,
)
from app.conversations.evolution_provider import (
    EvolutionConfigurationError,
    EvolutionSendError,
    send_evolution_text_message,
)
from app.appointment_service import mark_appointment_confirmed
from app.db import connection


async def prepare_appointment_confirmation_reminders(
    *,
    now: datetime | None = None,
) -> list[dict]:
    """
    Prépare les rappels WhatsApp de confirmation.

    Cette fonction :
    - ne contacte aucun fournisseur externe ;
    - ne confirme aucun rendez-vous ;
    - crée au maximum un rappel par rendez-vous ;
    - planifie le rappel à J-1 12:00 dans le fuseau de la clinique.
    """
    reference_now = now or datetime.now(timezone.utc)

    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=timezone.utc)

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    a.id AS appointment_id,
                    a.clinic_id,
                    a.patient_id,
                    a.start_at,
                    p.phone AS patient_phone,
                    c.timezone,
                    ci.provider,
                    ci.provider_instance
                FROM appointments a
                JOIN patients p
                  ON p.id = a.patient_id
                 AND p.clinic_id = a.clinic_id
                JOIN clinics c
                  ON c.id = a.clinic_id
                 AND c.active = TRUE
                JOIN LATERAL (
                    SELECT
                        provider,
                        provider_instance
                    FROM clinic_integrations
                    WHERE clinic_id = a.clinic_id
                      AND LOWER(BTRIM(provider)) = 'evolution'
                      AND active = TRUE
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                ) ci ON TRUE
                WHERE a.status = 'pending'
                  AND a.start_at > %s
                  AND NULLIF(BTRIM(p.phone), '') IS NOT NULL
                ORDER BY a.start_at
                """,
                (reference_now,),
            )

            appointments = await cur.fetchall()

            prepared: list[dict] = []

            for appointment in appointments:
                timezone_name = (
                    appointment.get("timezone")
                    or "Africa/Algiers"
                )

                try:
                    clinic_timezone = ZoneInfo(timezone_name)
                except Exception:
                    clinic_timezone = ZoneInfo("Africa/Algiers")

                appointment_local = appointment[
                    "start_at"
                ].astimezone(clinic_timezone)

                reminder_local_date = (
                    appointment_local.date()
                    - timedelta(days=1)
                )

                reminder_local = datetime.combine(
                    reminder_local_date,
                    time(hour=12),
                    tzinfo=clinic_timezone,
                )

                scheduled_for = reminder_local.astimezone(
                    timezone.utc
                )

                await cur.execute(
                    """
                    INSERT INTO appointment_confirmation_reminders (
                        clinic_id,
                        appointment_id,
                        patient_id,
                        provider,
                        provider_instance,
                        patient_phone,
                        status,
                        scheduled_for
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'pending',
                        %s
                    )
                    ON CONFLICT (appointment_id)
                    DO NOTHING
                    RETURNING *
                    """,
                    (
                        appointment["clinic_id"],
                        appointment["appointment_id"],
                        appointment["patient_id"],
                        appointment["provider"],
                        appointment["provider_instance"],
                        appointment["patient_phone"],
                        scheduled_for,
                    ),
                )

                reminder = await cur.fetchone()

                if reminder is not None:
                    prepared.append(reminder)

            await conn.commit()

            return prepared




def _build_confirmation_message(reminder: dict) -> str:
    patient_name = (
        reminder.get("patient_name")
        or "Bonjour"
    ).strip()

    clinic_name = (
        reminder.get("clinic_name")
        or "votre cabinet dentaire"
    ).strip()

    timezone_name = (
        reminder.get("timezone")
        or "Africa/Algiers"
    )

    try:
        clinic_timezone = ZoneInfo(timezone_name)
    except Exception:
        clinic_timezone = ZoneInfo("Africa/Algiers")

    appointment_local = reminder[
        "start_at"
    ].astimezone(clinic_timezone)

    treatment_label = (
        reminder.get("session_name")
        or reminder.get("treatment_name")
        or "votre rendez-vous"
    )

    return (
        f"Bonjour {patient_name},\n\n"
        f"Nous vous rappelons votre rendez-vous chez "
        f"{clinic_name} demain "
        f"{appointment_local.strftime('%d/%m/%Y')} "
        f"à {appointment_local.strftime('%H:%M')} "
        f"pour {treatment_label}.\n\n"
        "Merci de répondre OUI pour confirmer "
        "votre rendez-vous."
    )


async def dispatch_due_appointment_confirmation_reminders(
    *,
    now: datetime | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Envoie manuellement les rappels WhatsApp arrivés à échéance.

    Aucun scheduler n'appelle cette fonction automatiquement.

    Cycle :
    pending -> sending -> sent
                        -> failed

    Si le rendez-vous n'est plus pending :
    pending -> cancelled
    """
    reference_now = now or datetime.now(timezone.utc)

    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(
            tzinfo=timezone.utc
        )

    safe_limit = min(max(limit, 1), 100)

    results: list[dict] = []

    for _ in range(safe_limit):
        # --------------------------------------------------
        # 1. Réserver UN rappel dû + préparer le message local
        # --------------------------------------------------

        async with connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        r.*,
                        a.start_at,
                        a.status AS appointment_status,
                        p.full_name AS patient_name,
                        c.name AS clinic_name,
                        c.timezone,
                        t.name AS treatment_name,
                        ts.name AS session_name
                    FROM appointment_confirmation_reminders r
                    JOIN appointments a
                      ON a.id = r.appointment_id
                     AND a.clinic_id = r.clinic_id
                    JOIN patients p
                      ON p.id = r.patient_id
                     AND p.clinic_id = r.clinic_id
                    JOIN clinics c
                      ON c.id = r.clinic_id
                    LEFT JOIN treatments t
                      ON t.id = a.treatment_id
                     AND t.clinic_id = a.clinic_id
                    LEFT JOIN treatment_sessions ts
                      ON ts.id = a.treatment_session_id
                     AND ts.clinic_id = a.clinic_id
                    WHERE r.status = 'pending'
                      AND r.scheduled_for <= %s
                    ORDER BY r.scheduled_for
                    FOR UPDATE OF r SKIP LOCKED
                    LIMIT 1
                    """,
                    (reference_now,),
                )

                reminder = await cur.fetchone()

                if reminder is None:
                    break

                if reminder["appointment_status"] != "pending":
                    await cur.execute(
                        """
                        UPDATE appointment_confirmation_reminders
                        SET
                            status = 'cancelled',
                            error_message = NULL,
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING *
                        """,
                        (reminder["id"],),
                    )

                    cancelled = await cur.fetchone()

                    await conn.commit()

                    results.append(
                        {
                            "reminder": cancelled,
                            "result": "cancelled",
                            "reason": (
                                "appointment_not_pending"
                            ),
                        }
                    )

                    continue

                body = _build_confirmation_message(
                    reminder
                )

                thread = await get_or_create_conversation_thread(
                    cur=cur,
                    clinic_id=reminder["clinic_id"],
                    patient_id=reminder["patient_id"],
                    channel="whatsapp",
                    sender_phone=reminder["patient_phone"],
                    provider="evolution",
                    provider_instance=reminder[
                        "provider_instance"
                    ],
                    external_thread_id=None,
                )

                message = await create_conversation_message(
                    cur=cur,
                    clinic_id=reminder["clinic_id"],
                    thread_id=thread["id"],
                    patient_id=reminder["patient_id"],
                    channel="whatsapp",
                    direction="outbound",
                    author_type="system",
                    message_type="text",
                    body=body,
                    provider="evolution",
                    status="prepared",
                    requires_validation=False,
                    metadata={
                        "source": (
                            "appointment_confirmation_reminder"
                        ),
                        "provider_instance": reminder[
                            "provider_instance"
                        ],
                        "appointment_id": str(
                            reminder["appointment_id"]
                        ),
                        "reminder_id": str(
                            reminder["id"]
                        ),
                    },
                )

                await update_conversation_thread_after_message(
                    cur=cur,
                    thread_id=thread["id"],
                    direction="outbound",
                    patient_id=reminder["patient_id"],
                )

                await cur.execute(
                    """
                    UPDATE appointment_confirmation_reminders
                    SET
                        status = 'sending',
                        error_message = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                      AND status = 'pending'
                    RETURNING *
                    """,
                    (reminder["id"],),
                )

                sending = await cur.fetchone()

                if sending is None:
                    await conn.rollback()
                    continue

                await conn.commit()

        # --------------------------------------------------
        # 2. Appel Evolution HORS transaction DB
        # --------------------------------------------------

        try:
            provider_result = await send_evolution_text_message(
                instance=reminder["provider_instance"],
                sender_phone=reminder["patient_phone"],
                text=body,
            )

        except (
            EvolutionSendError,
            EvolutionConfigurationError,
            ValueError,
        ) as exc:
            # ----------------------------------------------
            # 3A. Échec
            # ----------------------------------------------

            async with connection() as conn:
                async with conn.cursor() as cur:
                    metadata_patch = {
                        "provider_delivery": {
                            "accepted": False,
                            "error": str(exc),
                        }
                    }

                    status_code = getattr(
                        exc,
                        "status_code",
                        None,
                    )

                    response_body = getattr(
                        exc,
                        "response_body",
                        None,
                    )

                    if status_code is not None:
                        metadata_patch[
                            "provider_delivery"
                        ]["status_code"] = status_code

                    if response_body:
                        metadata_patch[
                            "provider_delivery"
                        ]["response_body"] = response_body

                    failed_message = (
                        await update_conversation_message_status(
                            cur=cur,
                            clinic_id=reminder["clinic_id"],
                            message_id=message["id"],
                            status="failed",
                            metadata_patch=metadata_patch,
                        )
                    )

                    await cur.execute(
                        """
                        UPDATE appointment_confirmation_reminders
                        SET
                            status = 'failed',
                            error_message = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING *
                        """,
                        (
                            str(exc)[:2000],
                            reminder["id"],
                        ),
                    )

                    failed_reminder = await cur.fetchone()

                    await conn.commit()

            results.append(
                {
                    "reminder": failed_reminder,
                    "message": failed_message,
                    "result": "failed",
                    "error": str(exc),
                }
            )

            continue

        # --------------------------------------------------
        # 3B. Succès
        # --------------------------------------------------

        async with connection() as conn:
            async with conn.cursor() as cur:
                sent_message = (
                    await update_conversation_message_status(
                        cur=cur,
                        clinic_id=reminder["clinic_id"],
                        message_id=message["id"],
                        status="sent",
                        external_id=provider_result.get(
                            "external_id"
                        ),
                        metadata_patch={
                            "provider_delivery": {
                                "accepted": True,
                                "status_code": provider_result.get(
                                    "status_code"
                                ),
                                "response": provider_result.get(
                                    "response"
                                ),
                            }
                        },
                    )
                )

                await cur.execute(
                    """
                    UPDATE appointment_confirmation_reminders
                    SET
                        status = 'sent',
                        sent_at = NOW(),
                        external_message_id = %s,
                        error_message = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        provider_result.get("external_id"),
                        reminder["id"],
                    ),
                )

                sent_reminder = await cur.fetchone()

                await conn.commit()

        results.append(
            {
                "reminder": sent_reminder,
                "message": sent_message,
                "result": "sent",
            }
        )

    return results




def _normalize_confirmation_reply(value: str) -> str:
    normalized = value.strip().lower()

    replacements = {
        "’": "'",
        "‘": "'",
        "`": "'",
    }

    for source, target in replacements.items():
        normalized = normalized.replace(source, target)

    return " ".join(normalized.split())


def _is_positive_confirmation_reply(value: str) -> bool:
    normalized = _normalize_confirmation_reply(value)

    exact_positive = {
        "oui",
        "yes",
        "confirme",
        "confirmé",
        "je confirme",
        "ok",
        "okay",
        "oky",
        "oki",
        "d'accord",
        "daccord",
        "c'est bon",
        "cest bon",
        "oui merci",
        "oui je confirme",
        "oui d'accord",
        "oui daccord",
        "ok d'accord",
        "ok daccord",
    }

    if normalized in exact_positive:
        return True

    tokens = normalized.replace("'", "").split()

    if len(tokens) != 2:
        return False

    first, second = tokens

    if first not in {"oui", "ok", "okay"}:
        return False

    if len(second) > 8:
        return False

    # Tolérance très limitée aux fautes proches de "daccord".
    target = "daccord"

    if abs(len(second) - len(target)) > 1:
        return False

    mismatches = sum(
        left != right
        for left, right in zip(second, target)
    )

    mismatches += abs(
        len(second) - len(target)
    )

    return mismatches <= 2


async def handle_appointment_confirmation_reply(
    *,
    clinic_id: UUID,
    patient_phone: str,
    reply_text: str,
) -> dict | None:
    """
    Traite une réponse explicite à un rappel de confirmation.

    Retourne None si :
    - la réponse n'est pas une confirmation positive ;
    - aucun rappel envoyé ne correspond au numéro ;
    - le rendez-vous n'est plus pending.

    Sinon :
    - confirme le rendez-vous via la primitive métier existante ;
    - marque le reminder comme confirmed ;
    - conserve la réponse patient.
    """
    if not _is_positive_confirmation_reply(reply_text):
        return None

    normalized_phone = patient_phone.strip()

    if not normalized_phone:
        return None

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    r.id,
                    r.clinic_id,
                    r.appointment_id,
                    r.patient_id,
                    r.patient_phone,
                    r.status,
                    r.sent_at,
                    a.status AS appointment_status
                FROM appointment_confirmation_reminders r
                JOIN appointments a
                  ON a.id = r.appointment_id
                 AND a.clinic_id = r.clinic_id
                WHERE r.clinic_id = %s
                  AND r.status = 'sent'
                  AND a.status = 'pending'
                  AND r.patient_phone = %s
                ORDER BY
                    r.sent_at DESC NULLS LAST,
                    r.created_at DESC
                FOR UPDATE OF r
                LIMIT 1
                """,
                (
                    clinic_id,
                    normalized_phone,
                ),
            )

            reminder = await cur.fetchone()

            if reminder is None:
                return None

            appointment = await mark_appointment_confirmed(
                cur=cur,
                conn=conn,
                clinic_id=clinic_id,
                appointment_id=reminder["appointment_id"],
            )

            await cur.execute(
                """
                UPDATE appointment_confirmation_reminders
                SET
                    status = 'confirmed',
                    confirmed_at = NOW(),
                    patient_reply = %s,
                    error_message = NULL,
                    updated_at = NOW()
                WHERE id = %s
                  AND status = 'sent'
                RETURNING *
                """,
                (
                    reply_text.strip()[:2000],
                    reminder["id"],
                ),
            )

            confirmed_reminder = await cur.fetchone()

            if confirmed_reminder is None:
                return None

            await conn.commit()

            return {
                "appointment": appointment,
                "reminder": confirmed_reminder,
                "result": "confirmed",
            }


__all__ = [
    "dispatch_due_appointment_confirmation_reminders",
    "handle_appointment_confirmation_reply",
    "prepare_appointment_confirmation_reminders",
]
