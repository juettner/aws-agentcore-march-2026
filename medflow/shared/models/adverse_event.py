from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class AdverseEventCheckRequest:
    patient_id: str
    symptoms: List[str]
    medications: List[str]
    timeline: str
    vital_signs: Optional[Dict[str, float]] = None


@dataclass
class HistoricalCase:
    case_id: str
    patient_profile: Dict[str, str]
    symptoms: List[str]
    medications: List[str]
    timeline: str
    outcome: str
    severity_grade: int
    similarity_score: float


@dataclass
class AdverseEventResponse:
    patient_id: str
    severity_grade: int
    alert_generated: bool
    matched_patterns: List[str]
    historical_cases: List[HistoricalCase]
    confidence_score: float
    recommendation: str
    timestamp: datetime


@dataclass
class AdverseEventEpisode:
    episode_id: str
    patient_profile: Dict[str, str]
    symptoms: List[str]
    medications: List[str]
    timeline: str
    outcome: str
    severity_grade: int
    timestamp: datetime
