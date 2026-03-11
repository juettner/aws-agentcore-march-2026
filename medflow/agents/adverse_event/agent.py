import logging
from typing import List, Dict
from datetime import datetime
import uuid

from medflow.shared.models.adverse_event import (
    AdverseEventCheckRequest,
    AdverseEventResponse,
    AdverseEventEpisode,
    HistoricalCase,
)
from medflow.shared.utils.memory_client import MemoryClient

logger = logging.getLogger(__name__)


class AdverseEventMonitor:
    def __init__(self, memory_client: MemoryClient = None):
        self.memory_client = memory_client or MemoryClient()
        self.known_patterns = self._load_known_patterns()
        self.pattern_weights = self._initialize_pattern_weights()
        self.confidence_threshold = 0.8

    def check_adverse_event(
        self, request: AdverseEventCheckRequest
    ) -> AdverseEventResponse:
        logger.info(f"Checking adverse event for patient {request.patient_id}")

        historical_cases = self.memory_client.retrieve_similar_cases(
            request.symptoms, request.medications, request.timeline
        )

        severity_grade = self._calculate_severity(
            request.symptoms, request.medications, historical_cases
        )

        alert_generated = severity_grade >= 3

        matched_patterns = self._match_patterns(request.symptoms, request.medications)

        confidence_score = self._calculate_confidence(
            matched_patterns, historical_cases
        )

        recommendation = self._generate_recommendation(
            severity_grade, matched_patterns, historical_cases
        )

        if alert_generated:
            logger.warning(
                f"HIGH SEVERITY ALERT: Patient {request.patient_id} - Grade {severity_grade}"
            )

        return AdverseEventResponse(
            patient_id=request.patient_id,
            severity_grade=severity_grade,
            alert_generated=alert_generated,
            matched_patterns=matched_patterns,
            historical_cases=historical_cases,
            confidence_score=confidence_score,
            recommendation=recommendation,
            timestamp=datetime.now(),
        )

    def store_outcome(
        self,
        request: AdverseEventCheckRequest,
        outcome: str,
        severity_grade: int,
    ) -> bool:
        patient_profile = self._generalize_patient_profile(request)

        episode = AdverseEventEpisode(
            episode_id=str(uuid.uuid4()),
            patient_profile=patient_profile,
            symptoms=request.symptoms,
            medications=request.medications,
            timeline=request.timeline,
            outcome=outcome,
            severity_grade=severity_grade,
            timestamp=datetime.now(),
        )

        return self.memory_client.store_episode(episode)

    def _calculate_severity(
        self,
        symptoms: List[str],
        medications: List[str],
        historical_cases: List[HistoricalCase],
    ) -> int:
        base_severity = self._get_base_severity(symptoms)

        if historical_cases:
            avg_historical_severity = sum(
                case.severity_grade for case in historical_cases
            ) / len(historical_cases)
            severity = int((base_severity + avg_historical_severity) / 2)
        else:
            severity = base_severity

        return max(1, min(5, severity))

    def _get_base_severity(self, symptoms: List[str]) -> int:
        critical_symptoms = {
            "chest pain",
            "difficulty breathing",
            "severe bleeding",
            "loss of consciousness",
            "seizure",
        }
        severe_symptoms = {
            "high fever",
            "severe headache",
            "persistent vomiting",
            "confusion",
        }

        symptoms_lower = [s.lower() for s in symptoms]

        if any(cs in " ".join(symptoms_lower) for cs in critical_symptoms):
            return 5
        elif any(ss in " ".join(symptoms_lower) for ss in severe_symptoms):
            return 3
        else:
            return 1

    def _match_patterns(
        self, symptoms: List[str], medications: List[str]
    ) -> List[str]:
        matched = []
        for pattern_name, pattern_def in self.known_patterns.items():
            if self._pattern_matches(symptoms, medications, pattern_def):
                matched.append(pattern_name)
        return matched

    def _pattern_matches(
        self, symptoms: List[str], medications: List[str], pattern_def: Dict
    ) -> bool:
        symptoms_lower = " ".join([s.lower() for s in symptoms])
        medications_lower = " ".join([m.lower() for m in medications])

        required_symptoms = pattern_def.get("symptoms", [])
        required_meds = pattern_def.get("medications", [])

        symptoms_match = all(rs in symptoms_lower for rs in required_symptoms)
        meds_match = any(rm in medications_lower for rm in required_meds) if required_meds else True

        return symptoms_match and meds_match

    def _calculate_confidence(
        self, matched_patterns: List[str], historical_cases: List[HistoricalCase]
    ) -> float:
        if not matched_patterns and not historical_cases:
            return 0.3

        pattern_confidence = len(matched_patterns) * 0.2
        historical_confidence = min(len(historical_cases) * 0.1, 0.5)

        return min(pattern_confidence + historical_confidence, 1.0)

    def _generate_recommendation(
        self,
        severity_grade: int,
        matched_patterns: List[str],
        historical_cases: List[HistoricalCase],
    ) -> str:
        if severity_grade >= 4:
            return "URGENT: Immediate medical evaluation required. Contact physician immediately."
        elif severity_grade == 3:
            return "Contact physician within 24 hours for evaluation."
        elif matched_patterns:
            return f"Monitor symptoms. Known pattern: {matched_patterns[0]}."
        elif historical_cases:
            return "Monitor symptoms. Similar cases found in history."
        else:
            return "Continue monitoring. Report any worsening symptoms."

    def _generalize_patient_profile(
        self, request: AdverseEventCheckRequest
    ) -> Dict[str, str]:
        return {
            "age_range": "generalized",
            "gender": "generalized",
            "condition": "generalized",
        }

    def _load_known_patterns(self) -> Dict[str, Dict]:
        return {
            "cardiotoxicity": {
                "symptoms": ["chest pain", "palpitations"],
                "medications": ["doxorubicin", "trastuzumab"],
            },
            "hepatotoxicity": {
                "symptoms": ["jaundice", "abdominal pain"],
                "medications": ["acetaminophen", "methotrexate"],
            },
            "nephrotoxicity": {
                "symptoms": ["decreased urination", "swelling"],
                "medications": ["cisplatin", "gentamicin"],
            },
        }

    def _initialize_pattern_weights(self) -> Dict[str, float]:
        return {pattern: 1.0 for pattern in self.known_patterns.keys()}
