from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ConversationChannel = Literal[
    "whatsapp",
    "phone",
    "email",
    "sms",
    "web",
]

ConversationIntent = Literal[
    "greeting",
    "thanks",
    "goodbye",
    "book_appointment",
    "reschedule_appointment",
    "cancel_appointment",
    "clinic_information",
    "treatment_pricing",
    "dental_information",
    "preference_update",
    "human_handoff",
    "patient_registration",
    "unknown",
]


class ConversationRequest(BaseModel):
    channel: ConversationChannel

    sender_phone: str = Field(
        min_length=6,
        max_length=40,
    )

    message: str = Field(
        min_length=1,
        max_length=4000,
    )

    external_id: str | None = Field(
        default=None,
        max_length=255,
    )

    patient_id: UUID | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )


class ConversationInput(BaseModel):
    clinic_id: UUID
    channel: ConversationChannel

    sender_phone: str = Field(
        min_length=6,
        max_length=40,
    )

    message: str = Field(
        min_length=1,
        max_length=4000,
    )

    external_id: str | None = Field(
        default=None,
        max_length=255,
    )

    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    patient_id: UUID | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )


class ConversationAction(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    parameters: dict[str, Any] = Field(
        default_factory=dict,
    )


class ConversationResult(BaseModel):
    intent: ConversationIntent

    reply: str = Field(
        min_length=1,
        max_length=4000,
    )

    patient_id: UUID | None = None

    requires_human: bool = False

    actions: list[ConversationAction] = Field(
        default_factory=list,
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )
