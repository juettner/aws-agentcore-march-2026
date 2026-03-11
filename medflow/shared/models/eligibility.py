"""Data models for Patient Eligibility Agent."""

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class EligibilityRequest(BaseModel):
    patient_id: str = Field(..., alias="patientId")
    trial_id: str = Field(..., alias="trialId")
    request_timestamp: str = Field(..., alias="requestTimestamp")

    model_config = ConfigDict(populate_by_name=True)


class Citation(BaseModel):
    document_id: str = Field(..., alias="documentId")
    title: str
    page_number: Optional[int] = Field(None, alias="pageNumber")
    relevance_score: float = Field(..., alias="relevanceScore")

    model_config = ConfigDict(populate_by_name=True)


class CriterionEvaluation(BaseModel):
    criterion_id: str = Field(..., alias="criterionId")
    criterion_text: str = Field(..., alias="criterionText")
    result: Literal["pass", "fail", "unknown"]
    reasoning: str
    citations: list[Citation]

    model_config = ConfigDict(populate_by_name=True)


class EligibilityResponse(BaseModel):
    patient_id: str = Field(..., alias="patientId")
    trial_id: str = Field(..., alias="trialId")
    overall_eligibility: Literal["eligible", "ineligible", "conditional"] = Field(
        ..., alias="overallEligibility"
    )
    criteria_evaluations: list[CriterionEvaluation] = Field(
        ..., alias="criteriaEvaluations"
    )
    generated_at: str = Field(..., alias="generatedAt")

    model_config = ConfigDict(populate_by_name=True)
