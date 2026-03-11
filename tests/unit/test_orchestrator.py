"""Property and unit tests for Orchestrator Agent.

Property 1: Request Routing - every valid request type routes to the correct agent
Property 2: Result Aggregation - successful results are collected in the response
Property 3: Failure Handling - agent failures produce errors and escalation
"""

import pytest
from unittest.mock import patch
from hypothesis import given, settings
from hypothesis import strategies as st

from medflow.agents.orchestrator.agent import OrchestratorAgent, _REQUEST_TYPE_TO_AGENT
from medflow.shared.models.coordination import CoordinationRequest, Requester

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUEST_TYPES = list(_REQUEST_TYPE_TO_AGENT.keys())

PAYLOADS = {
    "patient_screening": {"patientId": "P001", "trialId": "T001"},
    "adverse_event_check": {"patientId": "P001", "symptoms": ["nausea"]},
    "regulatory_report": {"reportType": "IND_Safety", "trialId": "T001", "dateRange": {"start": "2024-01-01", "end": "2024-12-31"}},
    "insurance_auth": {"procedureCode": "99213", "cost": 450.0, "patientId": "P001"},
    "patient_checkin": {"patientId": "P001", "checkInType": "weekly"},
    "trial_scheduling": {"patientIds": ["P001", "P002"], "schedulingConstraints": {}},
}

REQUESTER = Requester(userId="user-1", role="coordinator", timestamp="2024-01-01T00:00:00Z")


def make_request(request_type: str) -> CoordinationRequest:
    return CoordinationRequest(
        requestId="req-001",
        requestType=request_type,
        priority="medium",
        payload=PAYLOADS[request_type],
        requester=REQUESTER,
    )


# ---------------------------------------------------------------------------
# Property 1: Request Routing
# Every valid request type routes to the correct specialist agent.
# ---------------------------------------------------------------------------

@given(request_type=st.sampled_from(REQUEST_TYPES))
@settings(max_examples=6)
def test_property_request_routing(request_type):
    """Each request type routes to the expected agent (reflected in errors when not implemented)."""
    orchestrator = OrchestratorAgent()
    request = make_request(request_type)

    response = orchestrator.coordinate(request)

    expected_agent = _REQUEST_TYPE_TO_AGENT[request_type]
    # Agents are stubs (NotImplementedError), so they appear in errors
    assert response.errors is not None
    assert any(e.agent_name == expected_agent for e in response.errors)


# ---------------------------------------------------------------------------
# Property 2: Result Aggregation
# Successful agent results are included in the response.
# ---------------------------------------------------------------------------

@given(request_type=st.sampled_from(REQUEST_TYPES))
@settings(max_examples=6)
def test_property_result_aggregation(request_type):
    """When an agent succeeds, its result appears in the response results list."""
    orchestrator = OrchestratorAgent()
    request = make_request(request_type)
    mock_result = {"status": "ok", "data": "test"}

    invoke_path = f"medflow.agents.orchestrator.agent.invoke_{_to_function_name(request_type)}"
    with patch(invoke_path, return_value=mock_result):
        response = orchestrator.coordinate(request)

    assert response.status == "completed"
    assert len(response.results) == 1
    assert response.results[0].agent_result == mock_result
    assert response.errors is None


# ---------------------------------------------------------------------------
# Property 3: Failure Handling
# Agent failures are logged as errors and trigger escalation.
# ---------------------------------------------------------------------------

@given(request_type=st.sampled_from(REQUEST_TYPES))
@settings(max_examples=6)
def test_property_failure_handling(request_type):
    """When an agent raises an exception, the response is escalated with error details."""
    orchestrator = OrchestratorAgent()
    request = make_request(request_type)

    invoke_path = f"medflow.agents.orchestrator.agent.invoke_{_to_function_name(request_type)}"
    with patch(invoke_path, side_effect=RuntimeError("downstream failure")):
        response = orchestrator.coordinate(request)

    assert response.status == "escalated"
    assert response.errors is not None
    assert len(response.errors) == 1
    assert "downstream failure" in response.errors[0].error_message
    assert response.escalation_reason is not None
    assert len(response.results) == 0


# ---------------------------------------------------------------------------
# Unit tests: specific scenarios
# ---------------------------------------------------------------------------

def test_coordinate_returns_request_id():
    orchestrator = OrchestratorAgent()
    request = make_request("patient_screening")
    response = orchestrator.coordinate(request)
    assert response.request_id == "req-001"


def test_partial_status_when_some_agents_fail():
    """partial status is not reachable with single-agent routing, but the logic is correct."""
    from medflow.agents.orchestrator.agent import _determine_status
    from medflow.shared.models.coordination import AgentResult, AgentError

    results = [AgentResult(agentName="A", agentResult={}, executionTime=0.1)]
    errors = [AgentError(agentName="B", errorMessage="fail", retryAttempts=0)]

    assert _determine_status(results, errors) == "partial"


def test_completed_status_with_no_errors():
    from medflow.agents.orchestrator.agent import _determine_status
    from medflow.shared.models.coordination import AgentResult

    results = [AgentResult(agentName="A", agentResult={}, executionTime=0.1)]
    assert _determine_status(results, []) == "completed"


def test_escalated_status_with_only_errors():
    from medflow.agents.orchestrator.agent import _determine_status
    from medflow.shared.models.coordination import AgentError

    errors = [AgentError(agentName="A", errorMessage="fail", retryAttempts=0)]
    assert _determine_status([], errors) == "escalated"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_function_name(request_type: str) -> str:
    """Map request_type to the invoke_* function name suffix."""
    mapping = {
        "patient_screening": "patient_eligibility_agent",
        "adverse_event_check": "adverse_event_monitor",
        "regulatory_report": "regulatory_report_agent",
        "insurance_auth": "insurance_authorization_agent",
        "patient_checkin": "patient_communication_agent",
        "trial_scheduling": "trial_coordinator_agent",
    }
    return mapping[request_type]
