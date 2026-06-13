"""FastAPI Pydantic request/response schemas."""
from __future__ import annotations
from typing import Any, Literal, Union
from pydantic import BaseModel, Field
import uuid


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class PlanRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    evaluation: dict[str, Any] | None = None


class PlanQuestionResponse(BaseModel):
    session_id: str
    type: Literal["question"] = "question"
    message: str
    collected_so_far: dict[str, Any]


class PlanCompleteResponse(BaseModel):
    session_id: str
    type: Literal["plan"] = "plan"
    plan: dict[str, Any]
    evaluation: dict[str, Any] | None = None


PlanResponse = Union[PlanQuestionResponse, PlanCompleteResponse]


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    env: str