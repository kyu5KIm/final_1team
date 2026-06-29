from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MinutesRequest(BaseModel):
    text: str = Field(..., description="STT transcript text.")
    meeting_id: str = ""
    project_id: str = ""
    title: str = ""
    meeting_datetime: str = ""
    location: str = ""
    project_context: str = ""


class AgendaRequest(BaseModel):
    title: str
    previous_summary: str = ""
    ocr_text: str = ""


class PreparationRequest(BaseModel):
    title: str = Field(..., description="Meeting topic or title used to generate preparation material.")
    preparation_id: str | int | None = None
    meeting_id: str = ""
    project_id: str = ""
    meeting_datetime: str = ""
    location: str = ""
    project_context: str = ""
    ocr_text: str = ""
    participants: list[dict[str, str]] = Field(default_factory=list)
    agendas: list[str] = Field(default_factory=list)
    max_previous_meetings: int = 5


class ChatRequest(BaseModel):
    question: str
    context: str = ""
    history: list[dict[str, str]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    project_id: str = ""
    meeting_id: str = ""
    source_scope: str = "project"
    source_types: list[str] = Field(default_factory=list)
    max_previous_meetings: int = 5
    min_relevance_score: float | None = None


class TextResponse(BaseModel):
    result: Any
    elapsed_sec: float
    model: str
