from app.ai.slot_selection import extract_selected_slot_index


def test_extract_second_suggested_slot_index() -> None:
    result = extract_selected_slot_index("le deuxième")

    assert result == 2
