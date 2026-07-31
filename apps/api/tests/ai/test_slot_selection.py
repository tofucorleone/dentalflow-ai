from app.ai.slot_selection import extract_selected_slot_index


def test_extract_second_suggested_slot_index() -> None:
    result = extract_selected_slot_index("le deuxième")

    assert result == 2


def test_extract_last_suggested_slot_marker() -> None:
    result = extract_selected_slot_index("le dernier")

    assert result == -1
