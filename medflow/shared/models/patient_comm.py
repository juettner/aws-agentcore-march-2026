from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class PatientCheckInRequest:
    patient_id: str
    scheduled_time: datetime
    audio_stream_url: Optional[str] = None


@dataclass
class ConversationTurn:
    speaker: str
    text: str
    timestamp: datetime
    interrupted: bool = False


@dataclass
class PatientCheckInResponse:
    patient_id: str
    conversation_id: str
    symptoms_reported: List[str]
    medication_adherence: Dict[str, bool]
    concerns_raised: List[str]
    escalation_required: bool
    transcript: List[ConversationTurn]
    audio_recording_url: str
    summary_generated_at: datetime
    duration_seconds: int
