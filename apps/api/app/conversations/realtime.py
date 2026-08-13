import asyncio
import json
import os
from collections.abc import AsyncIterator
from uuid import UUID

import redis.asyncio as redis


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://redis:6379/0",
)


def clinic_channel(
    clinic_id: UUID,
) -> str:
    return f"dentalflow:conversations:{clinic_id}"


async def publish_conversation_event(
    *,
    clinic_id: UUID,
    event_type: str,
    data: dict,
) -> int:
    client = redis.from_url(
        REDIS_URL,
        decode_responses=True,
    )

    payload = json.dumps(
        {
            "type": event_type,
            "data": data,
        },
        ensure_ascii=False,
        default=str,
    )

    try:
        subscribers = await client.publish(
            clinic_channel(clinic_id),
            payload,
        )
    finally:
        await client.aclose()

    return int(subscribers)


def format_sse_event(
    *,
    event_type: str,
    data: dict,
) -> str:
    payload = json.dumps(
        data,
        ensure_ascii=False,
        default=str,
    )

    return (
        f"event: {event_type}\n"
        f"data: {payload}\n\n"
    )


async def conversation_event_stream(
    *,
    clinic_id: UUID,
    heartbeat_seconds: float = 20.0,
) -> AsyncIterator[str]:
    client = redis.from_url(
        REDIS_URL,
        decode_responses=True,
    )

    pubsub = client.pubsub()

    try:
        await pubsub.subscribe(
            clinic_channel(clinic_id)
        )

        yield format_sse_event(
            event_type="connected",
            data={
                "clinic_id": str(clinic_id),
            },
        )

        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=heartbeat_seconds,
            )

            if message is None:
                yield format_sse_event(
                    event_type="heartbeat",
                    data={
                        "clinic_id": str(clinic_id),
                    },
                )
                continue

            raw_data = message.get("data")

            if not isinstance(raw_data, str):
                continue

            try:
                payload = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            event_type = str(
                payload.get("type") or "conversation"
            )

            event_data = payload.get("data")

            if not isinstance(event_data, dict):
                event_data = {
                    "value": event_data,
                }

            yield format_sse_event(
                event_type=event_type,
                data=event_data,
            )

            await asyncio.sleep(0)

    finally:
        try:
            await pubsub.unsubscribe(
                clinic_channel(clinic_id)
            )
        finally:
            await pubsub.aclose()
            await client.aclose()


__all__ = [
    "REDIS_URL",
    "clinic_channel",
    "conversation_event_stream",
    "format_sse_event",
    "publish_conversation_event",
]
