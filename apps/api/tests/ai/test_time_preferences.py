from datetime import time

from app.ai.time_preferences import parse_time_preference


def test_parse_after_time_preference() -> None:
    preference = parse_time_preference("après 15h")

    assert preference.earliest == time(15, 0)
    assert preference.latest is None
    assert preference.exact_time is None


def test_parse_before_time_preference() -> None:
    preference = parse_time_preference("avant 17h")

    assert preference.earliest is None
    assert preference.latest == time(17, 0)
    assert preference.exact_time is None


def test_parse_time_range_preference() -> None:
    preference = parse_time_preference("entre 14h et 16h")

    assert preference.earliest == time(14, 0)
    assert preference.latest == time(16, 0)
    assert preference.exact_time is None


def test_parse_after_work_preference() -> None:
    preference = parse_time_preference("après le travail")

    assert preference.earliest == time(17, 0)
    assert preference.latest == time(20, 0)
    assert preference.exact_time is None


def test_parse_after_boulot_preference() -> None:
    preference = parse_time_preference("après le boulot")

    assert preference.earliest == time(17, 0)
    assert preference.latest == time(20, 0)
    assert preference.exact_time is None
