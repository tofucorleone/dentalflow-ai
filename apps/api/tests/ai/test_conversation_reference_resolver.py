from app.ai.conversation_reference_resolver import (
    resolve_relative_reference,
)


def test_resolve_same_time_from_previous_start_at() -> None:
    result = resolve_relative_reference(
        message="à la même heure",
        context={
            "previous_start_at": "2026-08-05T15:30:00+01:00",
        },
    )

    assert result == "15h30"


def test_resolve_same_time_converts_utc_to_algiers_time() -> None:
    result = resolve_relative_reference(
        message="à la même heure",
        context={
            "previous_start_at": "2026-08-01T13:15:00+00:00",
        },
    )

    assert result == "14h15"


def test_resolve_previous_day_from_previous_start_at() -> None:
    result = resolve_relative_reference(
        message="la veille",
        context={
            "previous_start_at": "2026-08-01T13:15:00+00:00",
        },
    )

    assert result == "31 juillet 2026"


def test_resolve_next_day_from_previous_start_at() -> None:
    result = resolve_relative_reference(
        message="le lendemain",
        context={
            "previous_start_at": "2026-08-01T13:15:00+00:00",
        },
    )

    assert result == "2 aout 2026"



def test_resolve_one_hour_later_from_previous_start_at() -> None:
    result = resolve_relative_reference(
        message="une heure plus tard",
        context={
            "previous_start_at": "2026-08-01T13:15:00+00:00",
        },
    )

    assert result == "15h15"


def test_resolve_one_hour_earlier_from_previous_start_at() -> None:
    result = resolve_relative_reference(
        message="une heure plus tôt",
        context={
            "previous_start_at": "2026-08-01T13:15:00+00:00",
        },
    )

    assert result == "13h15"


def test_resolve_day_after_next_from_previous_start_at() -> None:
    result = resolve_relative_reference(
        message="le surlendemain",
        context={
            "previous_start_at": "2026-08-01T13:15:00+00:00",
        },
    )

    assert result == "3 aout 2026"


def test_resolve_day_before_previous_from_previous_start_at() -> None:
    result = resolve_relative_reference(
        message="l'avant-veille",
        context={
            "previous_start_at": "2026-08-01T13:15:00+00:00",
        },
    )

    assert result == "30 juillet 2026"
