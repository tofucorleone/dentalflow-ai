import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

from app.voice import twilio_router
from app.voice.twilio_media import TwilioMediaError


CLINIC_ID = UUID(
    "576a0895-f0f1-4e4f-b78c-c1d81d2da562"
)

CLINIC = {
    "id": CLINIC_ID,
    "name": "Clinique Dentaire Démo",
    "display_name": "Pour la vie",
    "phone": "+213000000000",
    "language": "fr",
}

RECORDING_URL = (
    "https://api.twilio.com/2010-04-01/"
    "Accounts/AC123/Recordings/RE123"
)


def test_twilio_recording_processes_valid_call(
    monkeypatch,
):
    clinic_mock = AsyncMock(return_value=CLINIC)
    download_mock = AsyncMock(
        return_value=b"fake-mp3-content"
    )
    transcription_mock = AsyncMock(
        return_value=(
            "Je voudrais prendre un rendez-vous "
            "vendredi après 17h"
        )
    )
    processor_mock = AsyncMock(
        return_value=SimpleNamespace(
            intent="book_appointment",
            reply=(
                "Les créneaux disponibles sont "
                "17 heures et 17 heures 30."
            ),
            requires_human=False,
        )
    )

    monkeypatch.setattr(
        twilio_router,
        "find_active_clinic_by_voice_number",
        clinic_mock,
    )
    monkeypatch.setattr(
        twilio_router,
        "download_twilio_recording_mp3",
        download_mock,
    )
    monkeypatch.setattr(
        twilio_router,
        "transcribe_audio",
        transcription_mock,
    )
    monkeypatch.setattr(
        twilio_router,
        "process_conversation",
        processor_mock,
    )

    response = asyncio.run(
        twilio_router.twilio_recording(
            CallSid="CA_TEST_001",
            From="+213542910065",
            To="+213000000000",
            RecordingUrl=RECORDING_URL,
            RecordingSid="RE123",
            RecordingDuration="6",
        )
    )

    body = response.body.decode()

    assert response.status_code == 200
    assert response.media_type == "application/xml"
    assert "Les créneaux disponibles" in body
    assert "<Record" in body
    assert "/voice/twilio/recording" in body

    clinic_mock.assert_awaited_once_with(
        "+213000000000",
    )
    download_mock.assert_awaited_once_with(
        RECORDING_URL,
    )
    transcription_mock.assert_awaited_once_with(
        filename="RE123.mp3",
        content=b"fake-mp3-content",
        language="fr",
    )

    conversation = processor_mock.await_args.args[0]

    assert conversation.clinic_id == CLINIC_ID
    assert conversation.channel == "phone"
    assert conversation.sender_phone == "+213542910065"
    assert conversation.session_id == "CA_TEST_001"
    assert conversation.external_id == "RE123"
    assert conversation.metadata["provider"] == "twilio"
    assert conversation.metadata["called_number"] == (
        "+213000000000"
    )


def test_twilio_recording_rejects_unknown_clinic(
    monkeypatch,
):
    clinic_mock = AsyncMock(return_value=None)
    download_mock = AsyncMock()

    monkeypatch.setattr(
        twilio_router,
        "find_active_clinic_by_voice_number",
        clinic_mock,
    )
    monkeypatch.setattr(
        twilio_router,
        "download_twilio_recording_mp3",
        download_mock,
    )

    response = asyncio.run(
        twilio_router.twilio_recording(
            CallSid="CA_UNKNOWN_CLINIC",
            From="+213542910065",
            To="+213999999999",
            RecordingUrl=RECORDING_URL,
            RecordingSid="RE_UNKNOWN",
            RecordingDuration="3",
        )
    )

    body = response.body.decode()

    assert response.status_code == 200
    assert "aucun cabinet actif" in body
    assert "<Hangup" in body
    assert "<Record" not in body

    download_mock.assert_not_awaited()


def test_twilio_recording_handles_media_error(
    monkeypatch,
):
    monkeypatch.setattr(
        twilio_router,
        "find_active_clinic_by_voice_number",
        AsyncMock(return_value=CLINIC),
    )
    monkeypatch.setattr(
        twilio_router,
        "download_twilio_recording_mp3",
        AsyncMock(
            side_effect=TwilioMediaError(
                "Média indisponible."
            )
        ),
    )

    transcription_mock = AsyncMock()
    processor_mock = AsyncMock()

    monkeypatch.setattr(
        twilio_router,
        "transcribe_audio",
        transcription_mock,
    )
    monkeypatch.setattr(
        twilio_router,
        "process_conversation",
        processor_mock,
    )

    response = asyncio.run(
        twilio_router.twilio_recording(
            CallSid="CA_MEDIA_ERROR",
            From="+213542910065",
            To="+213000000000",
            RecordingUrl=RECORDING_URL,
            RecordingSid="RE_MEDIA_ERROR",
            RecordingDuration="2",
        )
    )

    body = response.body.decode()

    assert "Je n'ai pas pu comprendre votre message" in body
    assert "<Hangup" in body
    assert "<Record" not in body

    transcription_mock.assert_not_awaited()
    processor_mock.assert_not_awaited()


def test_twilio_recording_stops_for_human_handoff(
    monkeypatch,
):
    monkeypatch.setattr(
        twilio_router,
        "find_active_clinic_by_voice_number",
        AsyncMock(return_value=CLINIC),
    )
    monkeypatch.setattr(
        twilio_router,
        "download_twilio_recording_mp3",
        AsyncMock(return_value=b"fake-audio"),
    )
    monkeypatch.setattr(
        twilio_router,
        "transcribe_audio",
        AsyncMock(
            return_value="Je souhaite parler à quelqu'un."
        ),
    )
    monkeypatch.setattr(
        twilio_router,
        "process_conversation",
        AsyncMock(
            return_value=SimpleNamespace(
                intent="human_handoff",
                reply=(
                    "Je vais vous mettre en relation "
                    "avec un membre du cabinet."
                ),
                requires_human=True,
            )
        ),
    )

    response = asyncio.run(
        twilio_router.twilio_recording(
            CallSid="CA_HANDOFF",
            From="+213542910065",
            To="+213000000000",
            RecordingUrl=RECORDING_URL,
            RecordingSid="RE_HANDOFF",
            RecordingDuration="4",
        )
    )

    body = response.body.decode()

    assert "mettre en relation" in body
    assert "<Hangup" in body
    assert "<Record" not in body
    assert (
        response.headers[
            "x-dentalflow-requires-human"
        ]
        == "true"
    )


def test_twilio_recording_stops_after_goodbye(
    monkeypatch,
):
    monkeypatch.setattr(
        twilio_router,
        "find_active_clinic_by_voice_number",
        AsyncMock(return_value=CLINIC),
    )
    monkeypatch.setattr(
        twilio_router,
        "download_twilio_recording_mp3",
        AsyncMock(return_value=b"fake-audio"),
    )
    monkeypatch.setattr(
        twilio_router,
        "transcribe_audio",
        AsyncMock(return_value="Au revoir."),
    )
    monkeypatch.setattr(
        twilio_router,
        "process_conversation",
        AsyncMock(
            return_value=SimpleNamespace(
                intent="goodbye",
                reply="Au revoir et bonne journée.",
                requires_human=False,
            )
        ),
    )

    response = asyncio.run(
        twilio_router.twilio_recording(
            CallSid="CA_GOODBYE",
            From="+213542910065",
            To="+213000000000",
            RecordingUrl=RECORDING_URL,
            RecordingSid="RE_GOODBYE",
            RecordingDuration="2",
        )
    )

    body = response.body.decode()

    assert "Au revoir et bonne journée" in body
    assert "<Hangup" in body
    assert "<Record" not in body
    assert response.headers["x-dentalflow-intent"] == (
        "goodbye"
    )
