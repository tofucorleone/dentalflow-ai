from app.ai.conversation_corrections import is_correction_message


def test_detects_correction_markers() -> None:
    assert is_correction_message("finalement jeudi") is True
    assert is_correction_message("en fait vendredi") is True
    assert is_correction_message("ah non, plutôt mardi") is True
    assert is_correction_message("non, plutôt à 17h") is True
    assert is_correction_message("plutôt le matin") is True
    assert is_correction_message("jeudi à 17h") is False


def test_detects_finalement_with_punctuation() -> None:
    assert is_correction_message("Finalement, jeudi") is True


def test_detects_en_fait_with_punctuation() -> None:
    assert is_correction_message("En fait, vendredi") is True


def test_detects_non_without_comma() -> None:
    assert is_correction_message("non plutot lundi") is True


def test_does_not_detect_regular_sentence() -> None:
    assert (
        is_correction_message(
            "je préfère le matin",
        )
        is False
    )
