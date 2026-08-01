from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ClinicBrandingPatch(BaseModel):
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )
    software_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )
    logo_url: str | None = Field(
        default=None,
        max_length=500,
    )
    background_image_url: str | None = Field(
        default=None,
        max_length=500,
    )
    primary_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )


class TreatmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    duration_minutes: int = Field(gt=0, le=480)
    price: Decimal = Field(ge=0)
    requires_consultation: bool = False
    active: bool = True


class TreatmentPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    duration_minutes: int | None = Field(default=None, gt=0, le=480)
    price: Decimal | None = Field(default=None, ge=0)
    requires_consultation: bool | None = None
    active: bool | None = None


class PractitionerIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    speciality: str | None = Field(default=None, max_length=150)
    google_calendar_id: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    active: bool = True


class PatientIn(BaseModel):
    phone: str = Field(min_length=6, max_length=40)
    full_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    administrative_notes: str | None = Field(default=None, max_length=2000)

class PatientPatch(BaseModel):
    phone: str | None = Field(default=None, min_length=6, max_length=40)
    full_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    administrative_notes: str | None = Field(
        default=None,
        max_length=2000,
    )

class AppointmentIn(BaseModel):
    patient_id: UUID
    practitioner_id: UUID | None = None
    treatment_id: UUID | None = None
    channel: Literal["whatsapp", "phone", "dashboard", "web"] = "dashboard"
    status: Literal["pending", "confirmed"] = "confirmed"
    start_at: datetime
    end_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("end_at doit être postérieur à start_at.")
        return self


class AppointmentRescheduleIn(BaseModel):
    start_at: datetime
    end_at: datetime | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("end_at doit être postérieur à start_at.")
        return self


class AvailabilityIn(BaseModel):
    practitioner_id: UUID | None = None
    treatment_id: UUID | None = None
    start_at: datetime
    end_at: datetime | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("end_at doit être postérieur à start_at.")
        return self
