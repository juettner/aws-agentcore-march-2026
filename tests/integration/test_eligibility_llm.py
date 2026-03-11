"""Live integration test for LLM-driven eligibility reasoning.

Requires real AWS credentials with bedrock:InvokeModel permission.
Run with: pytest tests/integration/test_eligibility_llm.py -v -m live
"""

import json
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from medflow.agents.patient_eligibility.agent import PatientEligibilityAgent
from medflow.shared.models.eligibility import EligibilityRequest
from medflow.shared.models.patient import (
    Demographics, Diagnosis, MedicalHistory,
    Medication, PatientRecord, VitalSigns,
)


@pytest.mark.live
def test_llm_reasoning_returns_valid_result():
    """Calls real Claude Haiku via Bedrock and verifies structured output."""
    patient = PatientRecord(
        patientId="P001",
        demographics=Demographics(age=45, gender="F"),
        medicalHistory=MedicalHistory(
            diagnoses=[Diagnosis(icd10Code="E11.9", description="Type 2 diabetes", diagnosisDate="2020-01-01")],
            allergies=["penicillin"],
            comorbidities=[],
        ),
        currentMedications=[
            Medication(drugName="Metformin", dosage="500mg", frequency="twice daily", startDate="2020-01-15")
        ],
        vitalSigns=VitalSigns(bloodPressure="120/80", heartRate=72, lastUpdated="2024-01-01"),
        labResults=[],
    )

    ehr_client = MagicMock()
    ehr_client.get_patient_record.return_value = patient

    kb_client = MagicMock()
    kb_client.retrieve_trial_protocol.return_value = {
        "inclusionCriteria": [
            {"criterionId": "C001", "criterionText": "Patient must be between 18 and 65 years old", "category": "demographic"},
            {"criterionId": "C002", "criterionText": "Patient must have a diagnosis of Type 2 diabetes", "category": "medical"},
        ],
        "exclusionCriteria": [
            {"criterionId": "C003", "criterionText": "Patient must not have a penicillin allergy", "category": "medical"},
        ],
    }
    kb_client.retrieve_medical_literature.return_value = []

    # Use real Bedrock — no mock on _bedrock
    agent = PatientEligibilityAgent(ehr_client=ehr_client, kb_client=kb_client)
    response = agent.evaluate(EligibilityRequest(
        patientId="P001",
        trialId="T001",
        requestTimestamp=datetime.now(timezone.utc).isoformat(),
    ))

    # Validate structure
    assert response.overall_eligibility in ("eligible", "ineligible", "conditional")
    assert len(response.criteria_evaluations) == 3

    for evaluation in response.criteria_evaluations:
        assert evaluation.result in ("pass", "fail", "unknown")
        assert len(evaluation.reasoning) > 10  # real sentence, not empty

    # Print reasoning so you can see the LLM output
    for e in response.criteria_evaluations:
        print(f"\n[{e.criterion_id}] {e.criterion_text}")
        print(f"  Result: {e.result}")
        print(f"  Reasoning: {e.reasoning}")

    print(f"\nOverall: {response.overall_eligibility}")
