from typing import Any
from pydantic import BaseModel, Field


class PatientNoteIn(BaseModel):
    author_name: str | None = Field(default=None, max_length=150)
    note: str = Field(min_length=1, max_length=5000)


class PatientMemoryIn(BaseModel):
    summary: str | None = Field(default=None, max_length=10000)
    preferences: dict[str, Any] = Field(default_factory=dict)
    last_goal: str | None = Field(default=None, max_length=500)
