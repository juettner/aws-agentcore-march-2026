"""Data models for Orchestrator Agent coordination requests and responses."""

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class Requester(BaseModel):
    user_id: str = Field(..., alias="userId")
    role: str
    timestamp: str

    model_config = ConfigDict(populate_by_name=True)


class CoordinationRequest(BaseModel):
    request_id: str = Field(..., alias="requestId")
    request_type: Literal[
        "patient_screening",
        "adverse_event_check",
        "regulatory_report",
        "insurance_auth",
        "patient_checkin",
        "trial_scheduling",
    ] = Field(..., alias="requestType")
    priority: Literal["low", "medium", "high", "urgent"]
    payload: dict[str, Any]
    requester: Requester

    model_config = ConfigDict(populate_by_name=True)


class AgentResult(BaseModel):
    agent_name: str = Field(..., alias="agentName")
    agent_result: Any = Field(..., alias="agentResult")
    execution_time: float = Field(..., alias="executionTime")

    model_config = ConfigDict(populate_by_name=True)


class AgentError(BaseModel):
    agent_name: str = Field(..., alias="agentName")
    error_message: str = Field(..., alias="errorMessage")
    retry_attempts: int = Field(..., alias="retryAttempts")

    model_config = ConfigDict(populate_by_name=True)


class CoordinationResponse(BaseModel):
    request_id: str = Field(..., alias="requestId")
    status: Literal["completed", "partial", "failed", "escalated"]
    results: list[AgentResult]
    errors: Optional[list[AgentError]] = None
    escalation_reason: Optional[str] = Field(None, alias="escalationReason")

    model_config = ConfigDict(populate_by_name=True)
