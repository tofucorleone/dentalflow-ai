import asyncio
import json
import os
from dataclasses import dataclass
from uuid import UUID, uuid4

import redis.asyncio as redis

from app.conversations.realtime import REDIS_URL


DEBOUNCE_SECONDS = float(
    os.getenv(
        "CONVERSATION_DEBOUNCE_SECONDS",
        "2.0",
    )
)

DEBOUNCE_TTL_SECONDS = max(
    10,
    int(DEBOUNCE_SECONDS) + 10,
)


@dataclass(frozen=True)
class DebouncedMessageBatch:
    should_process: bool
    message: str | None
    message_count: int
    degraded: bool = False


def _debounce_prefix(
    *,
    clinic_id: UUID,
    thread_id: UUID,
) -> str:
    return (
        "dentalflow:conversation-debounce:"
        f"{clinic_id}:{thread_id}"
    )


CLAIM_BATCH_SCRIPT = """
local current_token = redis.call("GET", KEYS[1])

if current_token ~= ARGV[1] then
    return {}
end

local messages = redis.call(
    "LRANGE",
    KEYS[2],
    0,
    -1
)

redis.call("DEL", KEYS[1])
redis.call("DEL", KEYS[2])

return messages
"""


async def debounce_conversation_message(
    *,
    clinic_id: UUID,
    thread_id: UUID,
    message: str,
) -> DebouncedMessageBatch:
    normalized_message = message.strip()

    if not normalized_message:
        return DebouncedMessageBatch(
            should_process=False,
            message=None,
            message_count=0,
        )

    prefix = _debounce_prefix(
        clinic_id=clinic_id,
        thread_id=thread_id,
    )

    token_key = f"{prefix}:token"
    messages_key = f"{prefix}:messages"
    token = uuid4().hex

    client = redis.from_url(
        REDIS_URL,
        decode_responses=True,
    )

    try:
        payload = json.dumps(
            {
                "message": normalized_message,
            },
            ensure_ascii=False,
        )

        pipeline = client.pipeline(
            transaction=True,
        )

        pipeline.rpush(
            messages_key,
            payload,
        )
        pipeline.expire(
            messages_key,
            DEBOUNCE_TTL_SECONDS,
        )
        pipeline.set(
            token_key,
            token,
            ex=DEBOUNCE_TTL_SECONDS,
        )

        await pipeline.execute()

        await asyncio.sleep(
            DEBOUNCE_SECONDS,
        )

        raw_messages = await client.eval(
            CLAIM_BATCH_SCRIPT,
            2,
            token_key,
            messages_key,
            token,
        )

        if not raw_messages:
            return DebouncedMessageBatch(
                should_process=False,
                message=None,
                message_count=0,
            )

        messages: list[str] = []

        for raw_message in raw_messages:
            try:
                item = json.loads(raw_message)
            except (
                TypeError,
                json.JSONDecodeError,
            ):
                continue

            value = str(
                item.get("message") or ""
            ).strip()

            if value:
                messages.append(value)

        if not messages:
            return DebouncedMessageBatch(
                should_process=False,
                message=None,
                message_count=0,
            )

        return DebouncedMessageBatch(
            should_process=True,
            message="\n".join(messages),
            message_count=len(messages),
        )

    except redis.RedisError:
        # Redis ne doit jamais empêcher le moteur
        # conversationnel de répondre.
        return DebouncedMessageBatch(
            should_process=True,
            message=normalized_message,
            message_count=1,
            degraded=True,
        )

    finally:
        await client.aclose()


__all__ = [
    "DEBOUNCE_SECONDS",
    "DebouncedMessageBatch",
    "debounce_conversation_message",
]
