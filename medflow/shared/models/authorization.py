"""Data models for Insurance Authorization Agent."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class AuthorizationRequest:
    """Request for insurance authorization."""

    patient_id: str
    procedure_code: str
    procedure_description: str
    estimated_cost: float
    provider_id: str


@dataclass
class AuthorizationResponse:
    """Response from insurance authorization."""

    authorization_id: str
    patient_id: str
    procedure_code: str
    decision: Literal["auto_approved", "supervisor_review", "human_escalation"]
    estimated_cost: float
    policy_evaluation: dict[str, bool]
    generated_at: str
