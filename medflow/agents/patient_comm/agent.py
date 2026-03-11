import logging
import uuid
from typing import List, Dict, AsyncIterator
from datetime import datetime

from medflow.shared.models.patient_comm import (
    PatientCheckInRequest,
    PatientCheckInResponse,
    ConversationTurn,
)
from medflow.shared.utils.nova_sonic_client import NovaSonicClient
from medflow.agents.adverse_event import AdverseEventMonitor
from medflow.shared.models.adverse_event import AdverseEventCheckRequest

logger = logging.getLogger(__name__)


class PatientCommunicationAgent:
    def __init__(
        self,
        nova_client: NovaSonicClient = None,
        adverse_event_monitor: AdverseEventMonitor = None,
    ):
        self.nova_client = nova_client or NovaSonicClient()
        self.adverse_event_monitor = adverse_event_monitor or AdverseEventMonitor()
        self.max_concurrent_streams = 10
        self.active_streams = 0
        self.full_responses = []
        
        self.standard_questions = [
            "How are you feeling today?",
            "Have you experienced any new symptoms since your last check-in?",
            "Are you taking your medications as prescribed?",
            "Have you noticed any side effects from your medications?",
            "Do you have any concerns you'd like to discuss?",
        ]
    
    async def conduct_check_in(
        self, request: PatientCheckInRequest
    ) -> PatientCheckInResponse:
        """Conduct voice check-in with patient using bidirectional streaming."""
        if self.active_streams >= self.max_concurrent_streams:
            raise RuntimeError("Maximum concurrent streams reached")
        
        self.active_streams += 1
        conversation_id = str(uuid.uuid4())
        transcript: List[ConversationTurn] = []
        symptoms_reported: List[str] = []
        medication_adherence: Dict[str, bool] = {}
        concerns_raised: List[str] = []
        self.full_responses = []
        
        start_time = datetime.now()
        
        try:
            context = {
                "current_question_index": 0,
                "agent_speaking": False,
                "patient_interrupted": False,
            }
            
            for question in self.standard_questions:
                agent_turn = ConversationTurn(
                    speaker="agent",
                    text=question,
                    timestamp=datetime.now(),
                    interrupted=False,
                )
                transcript.append(agent_turn)
                
                context["agent_speaking"] = True
                context["patient_interrupted"] = False
                
                async for audio_chunk in self.nova_client.text_to_speech_stream(question):
                    if self.nova_client.detect_interruption(0.5):
                        context["patient_interrupted"] = True
                        agent_turn.interrupted = True
                        break
                
                context["agent_speaking"] = False
                
                patient_response = await self._get_patient_response(context)
                
                if patient_response:
                    self.full_responses.append(patient_response)
                    patient_turn = ConversationTurn(
                        speaker="patient",
                        text=patient_response,
                        timestamp=datetime.now(),
                        interrupted=False,
                    )
                    transcript.append(patient_turn)
                    
                    self._extract_information(
                        question,
                        patient_response,
                        symptoms_reported,
                        medication_adherence,
                        concerns_raised,
                    )
            
            escalation_required = self._check_escalation(symptoms_reported)
            
            if escalation_required:
                await self._escalate_to_adverse_event_monitor(
                    request.patient_id, symptoms_reported, medication_adherence
                )
            
            end_time = datetime.now()
            duration = int((end_time - start_time).total_seconds())
            
            return PatientCheckInResponse(
                patient_id=request.patient_id,
                conversation_id=conversation_id,
                symptoms_reported=symptoms_reported,
                medication_adherence=medication_adherence,
                concerns_raised=concerns_raised,
                escalation_required=escalation_required,
                transcript=transcript,
                audio_recording_url=f"s3://medflow-recordings/{conversation_id}.wav",
                summary_generated_at=datetime.now(),
                duration_seconds=duration,
            )
            
        finally:
            self.active_streams -= 1
    
    async def _get_patient_response(self, context: Dict) -> str:
        """Get patient response via speech-to-text."""
        response_parts = []
        
        async for text_chunk in self.nova_client.speech_to_text_stream(None):
            response_parts.append(text_chunk)
            
            if text_chunk.endswith((".", "?", "!")):
                break
        
        return " ".join(response_parts)
    
    def _extract_information(
        self,
        question: str,
        response: str,
        symptoms: List[str],
        adherence: Dict[str, bool],
        concerns: List[str],
    ):
        """Extract structured information from patient response."""
        response_lower = response.lower()
        
        if "symptom" in question.lower():
            symptom_patterns = {
                "pain": ["pain"],
                "nausea": ["nausea", "nauseous"],
                "fever": ["fever"],
                "headache": ["headache"],
                "fatigue": ["fatigue", "tired"],
                "dizzy": ["dizzy", "dizziness"],
            }
            for symptom_name, patterns in symptom_patterns.items():
                if any(pattern in response_lower for pattern in patterns):
                    symptoms.append(symptom_name)
        
        if "medication" in question.lower():
            if "yes" in response_lower or "taking" in response_lower:
                adherence["prescribed_medications"] = True
            elif "no" in response_lower or "missed" in response_lower:
                adherence["prescribed_medications"] = False
        
        if "concern" in question.lower() or "worry" in question.lower():
            if len(response.split()) > 3:
                concerns.append(response)
    
    def _check_escalation(self, symptoms: List[str]) -> bool:
        """Check if symptoms require escalation to Adverse Event Monitor."""
        concerning_keywords = [
            "chest",
            "breathing",
            "bleeding",
            "confusion",
            "seizure",
        ]
        
        all_responses = " ".join(self.full_responses).lower()
        
        for keyword in concerning_keywords:
            if keyword in all_responses:
                return True
        
        for symptom in symptoms:
            if symptom in ["pain", "dizzy"]:
                if "chest" in all_responses or "severe" in all_responses:
                    return True
        
        return False
    
    async def _escalate_to_adverse_event_monitor(
        self, patient_id: str, symptoms: List[str], adherence: Dict[str, bool]
    ):
        """Escalate concerning symptoms to Adverse Event Monitor."""
        logger.warning(f"Escalating patient {patient_id} to Adverse Event Monitor")
        
        request = AdverseEventCheckRequest(
            patient_id=patient_id,
            symptoms=symptoms,
            medications=list(adherence.keys()),
            timeline="current check-in",
        )
        
        response = self.adverse_event_monitor.check_adverse_event(request)
        
        if response.alert_generated:
            logger.critical(
                f"HIGH SEVERITY ALERT from escalation: Patient {patient_id} - "
                f"Grade {response.severity_grade}"
            )
