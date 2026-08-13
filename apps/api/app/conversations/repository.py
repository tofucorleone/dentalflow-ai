from uuid import UUID


THREAD_SELECT = """
    SELECT
        t.id,
        t.clinic_id,
        t.patient_id,
        p.full_name AS patient_name,
        t.channel,
        t.sender_phone,
        t.provider,
        t.provider_instance,
        t.external_thread_id,
        t.assigned_user_id,
        t.status,
        t.unread_count,
        t.last_message_at,
        COALESCE(
            c.mode,
            'ai_active'
        ) AS control_mode,
        c.taken_over_by_user_id,
        c.taken_over_at,
        CASE
            WHEN lm.id IS NULL THEN NULL
            ELSE jsonb_build_object(
                'id',
                lm.id,
                'body',
                lm.body,
                'direction',
                lm.direction,
                'author_type',
                lm.author_type,
                'occurred_at',
                lm.occurred_at
            )
        END AS last_message,
        t.created_at,
        t.updated_at
    FROM conversation_threads t
    LEFT JOIN patients p
      ON p.id = t.patient_id
     AND p.clinic_id = t.clinic_id
    LEFT JOIN conversation_controls c
      ON c.clinic_id = t.clinic_id
     AND c.channel = t.channel
     AND c.sender_phone = t.sender_phone
    LEFT JOIN LATERAL (
        SELECT
            m.id,
            m.body,
            m.direction,
            m.author_type,
            m.occurred_at
        FROM conversation_messages m
        WHERE m.clinic_id = t.clinic_id
          AND m.thread_id = t.id
        ORDER BY
            m.occurred_at DESC,
            m.id DESC
        LIMIT 1
    ) lm ON TRUE
"""


async def count_conversation_threads(
    *,
    cur,
    clinic_id: UUID,
    status: str | None = None,
) -> int:
    query = """
        SELECT COUNT(*) AS total
        FROM conversation_threads
        WHERE clinic_id = %s
    """

    params: list = [
        clinic_id,
    ]

    if status is not None:
        query += """
          AND status = %s
        """
        params.append(status)

    await cur.execute(
        query,
        tuple(params),
    )

    row = await cur.fetchone()

    return int(row["total"])


async def list_conversation_threads(
    *,
    cur,
    clinic_id: UUID,
    limit: int,
    offset: int,
    status: str | None = None,
) -> list[dict]:
    query = (
        THREAD_SELECT
        + """
        WHERE t.clinic_id = %s
        """
    )

    params: list = [
        clinic_id,
    ]

    if status is not None:
        query += """
          AND t.status = %s
        """
        params.append(status)

    query += """
        ORDER BY
            t.last_message_at DESC NULLS LAST,
            t.updated_at DESC,
            t.id DESC
        LIMIT %s
        OFFSET %s
    """

    params.extend(
        [
            limit,
            offset,
        ]
    )

    await cur.execute(
        query,
        tuple(params),
    )

    return list(await cur.fetchall())


async def get_conversation_thread(
    *,
    cur,
    clinic_id: UUID,
    thread_id: UUID,
) -> dict | None:
    await cur.execute(
        THREAD_SELECT
        + """
        WHERE t.clinic_id = %s
          AND t.id = %s
        LIMIT 1
        """,
        (
            clinic_id,
            thread_id,
        ),
    )

    return await cur.fetchone()


async def mark_conversation_thread_read(
    *,
    cur,
    clinic_id: UUID,
    thread_id: UUID,
) -> dict | None:
    await cur.execute(
        """
        UPDATE conversation_threads
        SET
            unread_count = 0,
            updated_at = NOW()
        WHERE clinic_id = %s
          AND id = %s
        RETURNING
            id,
            unread_count,
            updated_at
        """,
        (
            clinic_id,
            thread_id,
        ),
    )

    return await cur.fetchone()


async def count_conversation_messages(
    *,
    cur,
    clinic_id: UUID,
    thread_id: UUID,
) -> int:
    await cur.execute(
        """
        SELECT COUNT(*) AS total
        FROM conversation_messages
        WHERE clinic_id = %s
          AND thread_id = %s
        """,
        (
            clinic_id,
            thread_id,
        ),
    )

    row = await cur.fetchone()

    return int(row["total"])


async def list_conversation_messages(
    *,
    cur,
    clinic_id: UUID,
    thread_id: UUID,
    limit: int,
    offset: int,
) -> list[dict]:
    await cur.execute(
        """
        SELECT
            id,
            clinic_id,
            thread_id,
            patient_id,
            sent_by_user_id,
            channel,
            direction,
            author_type,
            message_type,
            body,
            external_id,
            provider,
            status,
            requires_validation,
            metadata,
            occurred_at,
            created_at,
            updated_at
        FROM conversation_messages
        WHERE clinic_id = %s
          AND thread_id = %s
        ORDER BY
            occurred_at ASC,
            CASE
                WHEN direction = 'inbound' THEN 0
                ELSE 1
            END ASC,
            id ASC
        LIMIT %s
        OFFSET %s
        """,
        (
            clinic_id,
            thread_id,
            limit,
            offset,
        ),
    )

    return list(await cur.fetchall())


__all__ = [
    "count_conversation_messages",
    "count_conversation_threads",
    "get_conversation_thread",
    "list_conversation_messages",
    "list_conversation_threads",
    "mark_conversation_thread_read",
]
