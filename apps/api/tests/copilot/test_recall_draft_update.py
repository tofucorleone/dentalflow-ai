import asyncio
from uuid import uuid4

from app.copilot.service import update_recall_draft_message


class UpdateDraftCursor:
    def __init__(self, existing):
        self.existing = existing
        self.execute_count = 0
        self.query = None
        self.params = None
        self.row = None
        self.queries = []

    async def execute(self, query, params):
        self.execute_count += 1
        self.query = query
        self.params = params
        self.queries.append(query)

        if self.execute_count == 1:
            self.row = self.existing
            return

        if self.execute_count == 2:
            self.row = {
                **self.existing,
                "payload": {
                    **self.existing["payload"],
                    "message": params[0],
                },
            }
            return

        raise AssertionError(
            f"execute inattendu: {self.execute_count}"
        )

    async def fetchone(self):
        return self.row


def build_draft(*, status="draft"):
    return {
        "id": uuid4(),
        "clinic_id": uuid4(),
        "patient_id": uuid4(),
        "appointment_id": None,
        "channel": "whatsapp",
        "direction": "outbound",
        "event_type": "recall_draft",
        "external_id": None,
        "payload": {
            "status": status,
            "message": "Ancien message",
        },
        "created_at": None,
    }


def test_update_recall_draft_message_updates_active_draft():
    draft = build_draft()
    cursor = UpdateDraftCursor(draft)

    result = asyncio.run(
        update_recall_draft_message(
            cur=cursor,
            clinic_id=draft["clinic_id"],
            draft_id=draft["id"],
            message="  Nouveau message  ",
        )
    )

    assert cursor.execute_count == 2
    assert "FOR UPDATE" in cursor.queries[0]
    assert "UPDATE communication_events" in cursor.query
    assert "payload->>'status' = 'draft'" in cursor.query
    assert cursor.params[0] == "Nouveau message"

    assert (
        result["before"]["payload"]["message"]
        == "Ancien message"
    )
    assert (
        result["after"]["payload"]["message"]
        == "Nouveau message"
    )


def test_update_recall_draft_message_rejects_non_draft():
    draft = build_draft(status="sent")
    cursor = UpdateDraftCursor(draft)

    try:
        asyncio.run(
            update_recall_draft_message(
                cur=cursor,
                clinic_id=draft["clinic_id"],
                draft_id=draft["id"],
                message="Nouveau message",
            )
        )
    except RuntimeError as exc:
        assert (
            str(exc)
            == "Ce brouillon de rappel n’est plus modifiable."
        )
    else:
        raise AssertionError("RuntimeError attendue.")

    assert cursor.execute_count == 1


def test_update_recall_draft_message_rejects_missing_draft():
    cursor = UpdateDraftCursor(None)

    try:
        asyncio.run(
            update_recall_draft_message(
                cur=cursor,
                clinic_id=uuid4(),
                draft_id=uuid4(),
                message="Nouveau message",
            )
        )
    except LookupError as exc:
        assert str(exc) == "Brouillon de rappel introuvable."
    else:
        raise AssertionError("LookupError attendue.")

    assert cursor.execute_count == 1


def test_update_recall_draft_message_rejects_empty_message():
    cursor = UpdateDraftCursor(build_draft())

    try:
        asyncio.run(
            update_recall_draft_message(
                cur=cursor,
                clinic_id=uuid4(),
                draft_id=uuid4(),
                message="   ",
            )
        )
    except ValueError as exc:
        assert str(exc) == "Le brouillon ne peut pas être vide."
    else:
        raise AssertionError("ValueError attendue.")

    assert cursor.execute_count == 0
