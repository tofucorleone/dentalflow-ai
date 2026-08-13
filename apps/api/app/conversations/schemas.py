from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ConversationChannel = Literal[
    "whatsapp",
    "phone",
    "email",
    "sms",
    "web",
]

ConversationControlMode = Literal[
    "ai_active",
    "human_active",
    "paused",
    "closed",
]

ConversationThreadStatus = Literal[
    "open",
    "closed",
]

ConversationDirection = Literal[
    "inbound",
    "outbound",
]

ConversationAuthorType = Literal[
    "patient",
    "ai",
    "human",
    "system",
]

ConversationMessageType = Literal[
    "text",
    "image",
    "audio",
    "video",
    "document",
    "location",
    "system",
]

ConversationMessageStatus = Literal[
    "received",
    "prepared",
    "sent",
    "delivered",
    "read",
    "failed",
]


class ConversationLastMessage(BaseModel):
    id: UUID
    body: str | None
    direction: ConversationDirection
    author_type: ConversationAuthorType
    occurred_at: datetime


class ConversationThread(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID | None
    patient_name: str | None

    channel: ConversationChannel
    sender_phone: str

    provider: str | None
    provider_instance: str | None
    external_thread_id: str | None

    assigned_user_id: UUID | None
    status: ConversationThreadStatus

    unread_count: int
    last_message_at: datetime | None

    control_mode: ConversationControlMode
    taken_over_by_user_id: UUID | None
    taken_over_at: datetime | None

    last_message: ConversationLastMessage | None = None

    created_at: datetime
    updated_at: datetime


class ConversationThreadListResponse(BaseModel):
    items: list[ConversationThread] = Field(
        default_factory=list,
    )
    total: int
    limit: int
    offset: int


class ConversationMessage(BaseModel):
    id: UUID
    clinic_id: UUID
    thread_id: UUID
    patient_id: UUID | None
    sent_by_user_id: UUID | None

    channel: ConversationChannel
    direction: ConversationDirection
    author_type: ConversationAuthorType
    message_type: ConversationMessageType

    body: str | None
    external_id: str | None
    provider: str | None

    status: ConversationMessageStatus
    requires_validation: bool
    metadata: dict

    occurred_at: datetime
    created_at: datetime
    updated_at: datetime


class ConversationMessageListResponse(BaseModel):
    thread_id: UUID
    items: list[ConversationMessage] = Field(
        default_factory=list,
    )
    total: int
    limit: int
    offset: int


class ConversationSendRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=4000,
    )


class ConversationSendResponse(BaseModel):
    message: ConversationMessage



class ConversationExternalOutboundRequest(BaseModel):
    provider: str = Field(
        default="evolution",
        min_length=1,
        max_length=100,
    )
    sender_phone: str = Field(
        min_length=5,
        max_length=40,
    )
    message: str = Field(
        min_length=1,
        max_length=4000,
    )
    external_id: str = Field(
        min_length=1,
        max_length=255,
    )
    provider_instance: str = Field(
        min_length=1,
        max_length=255,
    )


class ConversationExternalOutboundResponse(BaseModel):
    message: ConversationMessage
    created: bool
