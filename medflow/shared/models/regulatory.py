"""Data models for Regulatory Report Agent."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class RegulatoryReportRequest:
    """Request for regulatory report generation."""

    report_type: Literal["IND_Safety", "IND_Annual", "NDA_Submission", "EMA_IMPD"]
    trial_id: str
    start_date: str
    end_date: str


@dataclass
class RegulatoryReportResponse:
    """Response from regulatory report generation."""

    report_id: str
    report_type: str
    trial_id: str
    format: Literal["FDA_21_CFR_312", "EMA_ICH_GCP"]
    pdf_url: str | None
    sections: list[str]
    missing_elements: list[str]
    generated_at: str
