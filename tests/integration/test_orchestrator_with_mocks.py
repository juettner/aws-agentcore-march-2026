"""Integration tests for Orchestrator Agent using mock specialist agents.

Verifies end-to-end orchestration flows for all 6 request types
without any external dependencies.
"""

import pytest
from unittest.mock import patch

from medflow.agents.orchestrator.agent import OrchestratorAgent
from medflow.agents import mocks
from medflow.shared.models.coordination import CoordinationRequest, Requester

REQUESTER = Requester(userId="user-1", role="coordinator", timestamp="2024-01-01T00:00:00Z")


def make_request(request_type: str, payload: dict) -> CoordinationRequest:
    return CoordinationRequest(
        requestId="req-001",
        requestType=request_type,
        priority="medium",
        payload=payload,
        requester=REQUESTER,
    )


MOCK_PATCHES = {
    "patient_screening": (
        "medflow.agents.orchestrator.agent.invoke_patient_eligibility_agent",
        lambda pid, tid: mocks.mock_patient_eligibility_agent(pid, tid),
    ),
    "adverse_event_check": (
        "medflow.agents.orchestrator.agent.invoke_adverse_event_monitor",
        lambda pid, symptoms: mocks.mock_adverse_event_monitor(pid, symptoms),
    ),
    "regulatory_report": (
        "medflow.agents.orchestrator.agent.invoke_regulatory_report_agent",
        lambda rt, tid, dr: mocks.mock_regulatory_report_agent(rt, tid, dr),
    ),
    "insurance_auth": (
        "medflow.agents.orchestrator.agent.invoke_insurance_authorization_agent",
        lambda pc, cost, pid: mocks.mock_insurance_authorization_agent(pc, cost, pid),
    ),
    "patient_checkin": (
        "medflow.agents.orchestrator.agent.invoke_patient_communication_agent",
        lambda pid, cit: mocks.mock_patient_communication_agent(pid, cit),
    ),
    "trial_scheduling": (
        "medflow.agents.orchestrator.agent.invoke_trial_coordinator_agent",
        lambda pids, sc: mocks.mock_trial_coordinator_agent(pids, sc),
    ),
}


@pytest.mark.parametrize("request_type,payload", [
    ("patient_screening", {"patientId": "P001", "trialId": "T001"}),
    ("adverse_event_check", {"patientId": "P001", "symptoms": ["nausea", "fatigue"]}),
    ("regulatory_report", {"reportType": "IND_Safety", "trialId": "T001", "dateRange": {"start": "2024-01-01", "end": "2024-12-31"}}),
    ("insurance_auth", {"procedureCode": "99213", "cost": 450.0, "patientId": "P001"}),
    ("patient_checkin", {"patientId": "P001", "checkInType": "routine"}),
    ("trial_scheduling", {"patientIds": ["P001", "P002", "P003"], "schedulingConstraints": {}}),
])
def test_orchestrator_with_mock_agent(request_type, payload):
    orchestrator = OrchestratorAgent()
    request = make_request(request_type, payload)
    patch_path, mock_fn = MOCK_PATCHES[request_type]

    with patch(patch_path, side_effect=mock_fn):
        response = orchestrator.coordinate(request)

    assert response.status == "completed"
    assert response.request_id == "req-001"
    assert len(response.results) == 1
    assert response.errors is None
    assert response.results[0].agent_result is not None


def test_insurance_auth_auto_approval_under_500():
    orchestrator = OrchestratorAgent()
    request = make_request("insurance_auth", {"procedureCode": "99213", "cost": 499.0, "patientId": "P001"})

    with patch("medflow.agents.orchestrator.agent.invoke_insurance_authorization_agent",
               side_effect=mocks.mock_insurance_authorization_agent):
        response = orchestrator.coordinate(request)

    assert response.results[0].agent_result["decision"] == "auto_approved"


def test_insurance_auth_supervisor_review_over_500():
    orchestrator = OrchestratorAgent()
    request = make_request("insurance_auth", {"procedureCode": "99213", "cost": 1500.0, "patientId": "P001"})

    with patch("medflow.agents.orchestrator.agent.invoke_insurance_authorization_agent",
               side_effect=mocks.mock_insurance_authorization_agent):
        response = orchestrator.coordinate(request)

    assert response.results[0].agent_result["decision"] == "supervisor_review"


def test_trial_scheduling_all_patients_scheduled():
    orchestrator = OrchestratorAgent()
    patient_ids = ["P001", "P002", "P003"]
    request = make_request("trial_scheduling", {"patientIds": patient_ids, "schedulingConstraints": {}})

    with patch("medflow.agents.orchestrator.agent.invoke_trial_coordinator_agent",
               side_effect=mocks.mock_trial_coordinator_agent):
        response = orchestrator.coordinate(request)

    result = response.results[0].agent_result
    assert result["scheduledPatients"] == 3
    assert result["conflicts"] == []
    scheduled_ids = [s["patientId"] for s in result["schedule"]]
    assert set(scheduled_ids) == set(patient_ids)
