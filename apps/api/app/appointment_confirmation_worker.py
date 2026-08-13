import asyncio
import os
from datetime import datetime, timezone

from app.appointment_confirmation_service import (
    dispatch_due_appointment_confirmation_reminders,
    prepare_appointment_confirmation_reminders,
)
from app.db import close_pool, open_pool


DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_DISPATCH_LIMIT = 20


def _positive_int_from_env(
    name: str,
    default: int,
) -> int:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        return default

    return value if value > 0 else default


async def run_cycle() -> None:
    prepared = (
        await prepare_appointment_confirmation_reminders()
    )

    dispatched = (
        await dispatch_due_appointment_confirmation_reminders(
            limit=_positive_int_from_env(
                "APPOINTMENT_CONFIRMATION_DISPATCH_LIMIT",
                DEFAULT_DISPATCH_LIMIT,
            )
        )
    )

    sent = sum(
        1
        for item in dispatched
        if item.get("result") == "sent"
    )

    failed = sum(
        1
        for item in dispatched
        if item.get("result") == "failed"
    )

    cancelled = sum(
        1
        for item in dispatched
        if item.get("result") == "cancelled"
    )

    print(
        "[appointment-confirmation-worker]",
        datetime.now(timezone.utc).isoformat(),
        f"prepared={len(prepared)}",
        f"processed={len(dispatched)}",
        f"sent={sent}",
        f"failed={failed}",
        f"cancelled={cancelled}",
        flush=True,
    )


async def main() -> None:
    interval_seconds = _positive_int_from_env(
        "APPOINTMENT_CONFIRMATION_WORKER_INTERVAL_SECONDS",
        DEFAULT_INTERVAL_SECONDS,
    )

    print(
        "[appointment-confirmation-worker]",
        f"starting interval={interval_seconds}s",
        flush=True,
    )

    await open_pool()

    try:
        while True:
            try:
                await run_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(
                    "[appointment-confirmation-worker]",
                    "cycle_failed",
                    repr(exc),
                    flush=True,
                )

            await asyncio.sleep(interval_seconds)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
