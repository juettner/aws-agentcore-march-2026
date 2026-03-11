"""Tests for Patient Eligibility Agent.

Property 4: Eligibility Criteria Completeness
Property 5: Eligibility Report Citations
Unit tests: specific eligibility scenarios and edge cases.
"""

import json
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from hypothesis import given, settings
from hypothesis import strategies as st

from medflow.agents.patient_eligibility.agent import PatientEligibilityAgent
from medflow.shared.models.eligibility import EligibilityRequest
from medflow.shared.models.patient import (
    Demographics, Diagnosis, MedicalHistory,
    Medication, PatientRecord, VitalSigns,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_patient(age=45, gender="F", diagnoses=None, allergies=None, comorbidities=None):
    return PatientRecord(
        patientId="P001",
        demographics=Demographics(age=age, gender=gender),
        medicalHistory=MedicalHistory(
            diagnoses=diagnoses or [
                Diagnosis(icd10Code="E11.9", description="Type 2 diabetes", diagnosisDate="2020-01-01")
            ],
            allergies=allergies or [],
            comorbidities=comorbidities or [],
        ),
        currentMedications=[
            Medication(drugName="Metformin", dosage="500mg", frequency="twice daily", startDate="2020-01-15")
        ],
        vitalSigns=VitalSigns(bloodPressure="120/80", heartRate=72, lastUpdated="2024-01-01"),
        labResults=[],
    )


def make_request(patient_id="P001", trial_id="T001"):
    return EligibilityRequest(
        patientId=patient_id,
        trialId=trial_id,
        requestTimestamp=datetime.now(timezone.utc).isoformat(),
    )


def llm_response(result="pass", reasoning="Patient meets criterion."):
    return {
        "output": {
            "message": {
                "content": [{"text": json.dumps({"result": result, "reasoning": reasoning})}]
            }
        }
    }


def make_agent(protocol, literature=None, llm_result="pass", llm_reasoning="Patient meets criterion."):
    ehr_client = MagicMock()
    ehr_client.get_patient_record.return_value = make_patient()

    kb_client = MagicMock()
    kb_client.retrieve_trial_protocol.return_value = protocol
    kb_client.retrieve_medical_literature.return_value = literature or []

    agent = PatientEligibilityAgent(ehr_client=ehr_client, kb_client=kb_client)
    agent._bedrock = MagicMock()
    agent._bedrock.converse.return_value = llm_response(llm_result, llm_reasoning)
    return agent


SAMPLE_PROTOCOL = {
    "inclusionCriteria": [
        {"criterionId": "C001", "criterionText": "Age 18-65", "category": "demographic"},
        {"criterionId": "C002", "criterionText": "Diagnosis of Type 2 diabetes", "category": "medical"},
    ],
    "exclusionCriteria": [
        {"criterionId": "C003", "criterionText": "Allergy to penicillin", "category": "medical"},
    ],
}

SAMPLE_CITATIONS = [
    {"documentId": "DOC-001", "title": "Trial Protocol v1.0", "pageNumber": 12, "relevanceScore": 0.95},
]


# ---------------------------------------------------------------------------
# Property 4: Criteria Completeness
# ---------------------------------------------------------------------------

@given(
    inclusion_count=st.integers(min_value=0, max_value=5),
    exclusion_count=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=20)
def test_property_criteria_completeness(inclusion_count, exclusion_count):
    protocol = {
        "inclusionCriteria": [
            {"criterionId": f"I{i:03d}", "criterionText": f"Inclusion criterion {i}", "category": "medical"}
            for i in range(inclusion_count)
        ],
        "exclusionCriteria": [
            {"criterionId": f"E{i:03d}", "criterionText": f"Exclusion criterion {i}", "category": "medical"}
            for i in range(exclusion_count)
        ],
    }
    agent = make_agent(protocol)
    response = agent.evaluate(make_request())

    expected_ids = (
        {c["criterionId"] for c in protocol["inclusionCriteria"]}
        | {c["criterionId"] for c in protocol["exclusionCriteria"]}
    )
    actual_ids = {e.criterion_id for e in response.criteria_evaluations}
    assert actual_ids == expected_ids


# ---------------------------------------------------------------------------
# Property 5: Citation Inclusion
# ---------------------------------------------------------------------------

@given(criterion_count=st.integers(min_value=1, max_value=5))
@settings(max_examples=10)
def test_property_citation_inclusion(criterion_count):
    protocol = {
        "inclusionCriteria": [
            {"criterionId": f"C{i:03d}", "criterionText": f"Criterion {i}", "category": "medical"}
            for i in range(criterion_count)
        ],
        "exclusionCriteria": [],
    }
    agent = make_agent(protocol, literature=SAMPLE_CITATIONS)
    response = agent.evaluate(make_request())

    for evaluation in response.criteria_evaluations:
        assert len(evaluation.citations) > 0


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_eligible_patient_with_complete_data():
    agent = make_agent(SAMPLE_PROTOCOL, literature=SAMPLE_CITATIONS)
    response = agent.evaluate(make_request())

    assert response.patient_id == "P001"
    assert response.trial_id == "T001"
    assert len(response.criteria_evaluations) == 3
    assert response.generated_at is not None


def test_ineligible_patient_fails_exclusion_criterion():
    agent = make_agent(
        SAMPLE_PROTOCOL,
        llm_result="fail",
        llm_reasoning="Patient has penicillin allergy which is an exclusion criterion.",
    )
    response = agent.evaluate(make_request())

    assert response.overall_eligibility == "ineligible"
    exclusion_eval = next(e for e in response.criteria_evaluations if e.criterion_id == "C003")
    assert exclusion_eval.result == "fail"
    assert "penicillin" in exclusion_eval.reasoning


def test_patient_too_young_fails_age_inclusion():
    ehr_client = MagicMock()
    ehr_client.get_patient_record.return_value = make_patient(age=16)

    kb_client = MagicMock()
    kb_client.retrieve_trial_protocol.return_value = {
        "inclusionCriteria": [
            {"criterionId": "C001", "criterionText": "Age 18-65", "category": "demographic"}
        ],
        "exclusionCriteria": [],
    }
    kb_client.retrieve_medical_literature.return_value = []

    agent = PatientEligibilityAgent(ehr_client=ehr_client, kb_client=kb_client)
    agent._bedrock = MagicMock()
    agent._bedrock.converse.return_value = llm_response(
        "fail", "Patient is 16 years old, below the minimum age of 18."
    )

    response = agent.evaluate(make_request())
    assert response.overall_eligibility == "ineligible"
    assert response.criteria_evaluations[0].result == "fail"


def test_empty_trial_protocol_returns_conditional():
    agent = make_agent({"inclusionCriteria": [], "exclusionCriteria": []})
    response = agent.evaluate(make_request())

    assert response.overall_eligibility == "conditional"
    assert response.criteria_evaluations == []


def test_missing_patient_data_returns_unknown_criteria():
    ehr_client = MagicMock()
    ehr_client.get_patient_record.return_value = make_patient(diagnoses=[], allergies=[], comorbidities=[])

    kb_client = MagicMock()
    kb_client.retrieve_trial_protocol.return_value = {
        "inclusionCriteria": [
            {"criterionId": "C001", "criterionText": "Has cardiovascular disease", "category": "medical"}
        ],
        "exclusionCriteria": [],
    }
    kb_client.retrieve_medical_literature.return_value = []

    agent = PatientEligibilityAgent(ehr_client=ehr_client, kb_client=kb_client)
    agent._bedrock = MagicMock()
    agent._bedrock.converse.return_value = llm_response(
        "unknown", "No cardiovascular diagnosis found in patient record."
    )

    response = agent.evaluate(make_request())
    assert response.overall_eligibility == "conditional"
    assert response.criteria_evaluations[0].result == "unknown"


def test_patient_meets_all_inclusion_but_one_exclusion():
    ehr_client = MagicMock()
    ehr_client.get_patient_record.return_value = make_patient(
        age=40,
        diagnoses=[Diagnosis(icd10Code="E11.9", description="Type 2 diabetes", diagnosisDate="2020-01-01")],
        allergies=["penicillin"],
    )

    kb_client = MagicMock()
    kb_client.retrieve_trial_protocol.return_value = {
        "inclusionCriteria": [
            {"criterionId": "C001", "criterionText": "Age 18-65", "category": "demographic"},
            {"criterionId": "C002", "criterionText": "Diagnosis of Type 2 diabetes", "category": "medical"},
        ],
        "exclusionCriteria": [
            {"criterionId": "C003", "criterionText": "Allergy to penicillin", "category": "medical"},
        ],
    }
    kb_client.retrieve_medical_literature.return_value = []

    agent = PatientEligibilityAgent(ehr_client=ehr_client, kb_client=kb_client)
    agent._bedrock = MagicMock()
    agent._bedrock.converse.side_effect = [
        llm_response("pass", "Age 40 is within 18-65 range."),
        llm_response("pass", "Patient has Type 2 diabetes diagnosis."),
        llm_response("fail", "Patient has penicillin allergy which is an exclusion criterion."),
    ]

    response = agent.evaluate(make_request())
    assert response.overall_eligibility == "ineligible"
