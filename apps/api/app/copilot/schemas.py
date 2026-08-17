from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


AppointmentStatus = Literal[
    "pending",
    "confirmed",
    "cancelled",
    "completed",
    "no_show",
]


class CopilotAppointment(BaseModel):
    id: UUID
    patient_id: UUID
    practitioner_id: UUID | None
    treatment_id: UUID | None
    patient_name: str | None
    practitioner_name: str | None
    treatment_name: str | None
    channel: Literal["whatsapp", "phone", "dashboard", "web"]
    status: AppointmentStatus
    start_at: datetime
    end_at: datetime
    notes: str | None


class CopilotSummary(BaseModel):
    total: int
    pending: int
    confirmed: int
    cancelled: int
    completed: int
    no_show: int
    active: int
    upcoming: int


class CopilotPriorities(BaseModel):
    pending_confirmation: int
    cancelled_today: int
    no_show: int
    late_active: int




class CopilotRecallCandidate(BaseModel):
    patient_id: UUID
    patient_name: str | None
    score: int
    match_level: Literal["primary", "secondary"]
    reasons: list[str]
    requires_validation: bool
    draft_message: str


class CopilotOverdueRecallPatient(BaseModel):
    patient_id: UUID
    patient_name: str | None
    phone: str
    email: str | None
    last_completed_at: datetime
    score: int
    priority: Literal["high","medium","low"]
    reasons: list[str]
    draft_message: str


class CopilotReleasedSlot(BaseModel):
    appointment_id: UUID
    cancelled_patient_id: UUID
    practitioner_id: UUID | None
    practitioner_name: str | None
    treatment_id: UUID | None = None
    start_at: datetime
    end_at: datetime
    recall_candidates: list[CopilotRecallCandidate] = []


class CopilotAction(BaseModel):
    id: str
    priority: Literal["high", "medium", "low"]
    score: int
    title: str
    description: str
    recommended_action: str
    requires_validation: bool = False


class CopilotUserContext(BaseModel):
    id: UUID
    full_name: str | None
    role: Literal["owner", "admin", "staff"]



class AppointmentMessageDraftCreateRequest(BaseModel):
    patient_id: UUID
    appointment_id: UUID
    message_kind: Literal[
        "pending_confirmation",
        "no_show",
    ]
    message: str = Field(
        min_length=1,
        max_length=4000,
    )


class AppointmentMessageDraftResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    appointment_id: UUID
    channel: Literal["whatsapp"]
    direction: Literal["outbound"]
    event_type: Literal["appointment_message_draft"]
    external_id: str | None
    payload: dict
    created_at: datetime


class AppointmentMessageSendRequest(BaseModel):
    draft_id: UUID
    patient_id: UUID
    appointment_id: UUID
    message_kind: Literal[
        "pending_confirmation",
        "no_show",
    ]
    message: str = Field(
        min_length=1,
        max_length=4000,
    )


class RecallDraftCreateRequest(BaseModel):
    patient_id: UUID
    appointment_id: UUID | None = None
    message: str
    candidate_score: int
    match_level: Literal[
        "primary",
        "secondary",
        "preventive",
    ]
    reasons: list[str] = []


class RecallDraftUpdateRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=4000,
    )


class RecallDraftResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    appointment_id: UUID | None
    channel: Literal["whatsapp"]
    direction: Literal["outbound"]
    event_type: Literal["recall_draft"]
    external_id: str | None
    payload: dict
    created_at: datetime



class RecallSendRequest(BaseModel):
    draft_id: UUID
    patient_id: UUID
    appointment_id: UUID | None = None
    practitioner_id: UUID | None = None
    treatment_id: UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    message: str = Field(
        min_length=1,
        max_length=4000,
    )


class CopilotChatRequest(BaseModel):
    message: str


class CopilotChatAction(BaseModel):
    type: Literal["navigate"]
    label: str
    href: str


class CopilotChatSource(BaseModel):
    type: Literal[
        "patient",
        "practitioner",
        "appointment",
    ]
    id: UUID
    label: str


class CopilotChatResponse(BaseModel):
    answer: str
    intent: Literal[
        "open_patient",
        "patient_search",
        "next_practitioner_appointment",
        "practitioner_search",
        "patient_next_appointment",
        "planner_summary",
        "recall",
        "schedule",
        "navigation",
        "unsupported",
    ]
    actions: list[CopilotChatAction] = []
    sources: list[CopilotChatSource] = []
    suggestions: list[str] = []
    requires_validation: bool = False


class CopilotPlannerAction(BaseModel):
    id: str
    type: Literal[
        "recall",
        "released_slot",
        "late_active",
        "pending_confirmation",
    ]
    priority: Literal["high", "medium", "low"]
    score: int
    title: str
    description: str
    actions: list[CopilotChatAction] = []
    requires_validation: bool = False


class CopilotTask(BaseModel):
    id: str
    type: Literal[
        "recall",
        "released_slot",
        "late_active",
        "pending_confirmation",
        "no_show",
        "conversation_reply",
    ]
    priority: Literal["high", "medium", "low"]
    score: int
    title: str
    description: str
    recommended_action: str
    patient_id: UUID | None = None
    appointment_id: UUID | None = None
    draft_id: UUID | None = None
    draft_message: str | None = None
    reasons: list[str] = []
    status: Literal[
        "open",
        "prepared",
        "completed",
        "dismissed",
        "snoozed",
    ] = "open"
    assigned_user_id: UUID | None = None
    snoozed_until: datetime | None = None
    completed_at: datetime | None = None
    requires_validation: bool = False
    actions: list[CopilotChatAction] = []


class CopilotPlannerResponse(BaseModel):
    generated_at: datetime
    timezone: str
    clinic_id: UUID
    priorities: CopilotPriorities
    recommended_actions: list[CopilotPlannerAction] = []
    released_slots: list[CopilotReleasedSlot] = []
    overdue_recall_patients: list[CopilotOverdueRecallPatient] = []
    appointments: list[CopilotAppointment] = []


class DailyBriefResponse(BaseModel):
    date: date
    timezone: str
    clinic_id: UUID
    user: CopilotUserContext
    summary: CopilotSummary
    priorities: CopilotPriorities
    actions: list[CopilotAction] = []
    released_slots: list[CopilotReleasedSlot] = []
    overdue_recall_patients: list[CopilotOverdueRecallPatient] = []
    appointments: list[CopilotAppointment]


class CopilotConversationAction(BaseModel):
    type: Literal[
        "review_urgent",
        "prepare_appointment",
        "prepare_reschedule",
        "prepare_cancellation",
        "link_patient",
        "review_conversation",
    ]
    label: str
    description: str
    requires_validation: bool = False


class CopilotPatientAppointmentSummary(BaseModel):
    id: UUID
    status: AppointmentStatus
    start_at: datetime
    end_at: datetime
    practitioner_name: str | None
    treatment_name: str | None


class CopilotPatientTimelineEvent(BaseModel):
    id: str
    type: Literal[
        "appointment",
        "conversation",
        "note",
    ]
    occurred_at: datetime
    title: str
    description: str | None = None
    status: str | None = None
    direction: Literal["inbound", "outbound"] | None = None


class CopilotPatientContext(BaseModel):
    identified: bool
    full_name: str | None = None
    phone: str | None = None
    ai_summary: str | None = None
    last_goal: str | None = None
    preferences: dict = {}
    recent_notes: list[str] = []
    medical_history: list[str] = []
    next_appointment: CopilotPatientAppointmentSummary | None = None
    last_completed_appointment: CopilotPatientAppointmentSummary | None = None


class CopilotConversationInsight(BaseModel):
    thread_id: UUID
    patient_id: UUID | None
    patient_name: str | None
    sender_phone: str
    summary: str
    priority: Literal["high", "medium", "low"]
    priority_score: int
    priority_reasons: list[str] = []
    intents: list[str] = []
    recommended_actions: list[CopilotConversationAction] = []
    message_count: int
    control_mode: Literal[
        "ai_active",
        "human_active",
        "paused",
        "closed",
    ]
    last_message_at: datetime | None
    patient_context: CopilotPatientContext
    patient_timeline: list[CopilotPatientTimelineEvent] = []
    read_only: Literal[True] = True


class CopilotConversationControlRequest(BaseModel):
    mode: Literal["ai_active", "human_active"]


class CopilotConversationControlResponse(BaseModel):
    thread_id: UUID
    mode: Literal["ai_active", "human_active"]
    taken_over_by_user_id: UUID | None = None
    taken_over_at: datetime | None = None


class CopilotAuditEvent(BaseModel):
    id: UUID
    clinic_id: UUID
    thread_id: UUID | None = None
    patient_id: UUID | None = None
    actor_user_id: UUID | None = None
    action_type: str
    result: Literal["success", "failed", "prepared"]
    entity_type: str | None = None
    entity_id: UUID | None = None
    before_data: dict = {}
    after_data: dict = {}
    metadata: dict = {}
    created_at: datetime

class CopilotAuditListResponse(BaseModel):
    thread_id: UUID
    items: list[CopilotAuditEvent] = []

class CopilotDashboardRecommendation(BaseModel):
    id: str
    type: str
    priority: Literal["high", "medium", "low"]
    title: str
    description: str
    href: str | None = None


class CopilotDashboardOverview(BaseModel):
    generated_at: datetime
    timezone: str
    clinic_id: UUID
    unread_messages: int
    unread_threads: int
    pending_confirmations: int
    patients_to_recall: int
    late_active: int
    released_slots: int
    alerts: int
    recommendations: list[CopilotDashboardRecommendation] = []



class CopilotTaskStateUpdateRequest(BaseModel):
    status: Literal[
        "open",
        "prepared",
        "completed",
        "dismissed",
        "snoozed",
    ]
    snoozed_until: datetime | None = None
    assign_to_me: bool = False
