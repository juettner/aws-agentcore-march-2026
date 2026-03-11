from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class MessageType(Enum):
    PROPOSAL = "proposal"
    CONFLICT = "conflict"
    NEGOTIATION = "negotiation"
    CONFIRMATION = "confirmation"
    BROADCAST = "broadcast"


@dataclass
class A2AMessage:
    message_id: str
    sender_id: str
    recipient_id: Optional[str]
    message_type: MessageType
    payload: Dict
    timestamp: datetime
    broadcast: bool = False


@dataclass
class TimeSlot:
    start_time: datetime
    end_time: datetime
    resource_id: str
    patient_id: str


@dataclass
class SchedulingProposal:
    proposal_id: str
    patient_id: str
    time_slots: List[TimeSlot]
    priority: int


@dataclass
class TrialSchedulingRequest:
    trial_id: str
    patient_ids: List[str]
    available_resources: List[str]
    scheduling_window_start: datetime
    scheduling_window_end: datetime


@dataclass
class PatientSchedule:
    patient_id: str
    assigned_slots: List[TimeSlot]
    status: str


@dataclass
class TrialSchedulingResponse:
    trial_id: str
    schedules: List[PatientSchedule]
    conflicts_resolved: int
    total_messages_exchanged: int
    completion_time: datetime
    resource_usage_peak: float
