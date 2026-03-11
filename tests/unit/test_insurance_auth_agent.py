"""Unit tests for Insurance Authorization Agent."""

import pytest

from medflow.agents.insurance_auth import InsuranceAuthorizationAgent
from medflow.shared.models.authorization import AuthorizationRequest


def test_auto_approval_for_low_cost():
    """Test auto-approval for $499 procedure."""
    agent = InsuranceAuthorizationAgent()
    
    request = AuthorizationRequest(
        patient_id="PAT-001",
        procedure_code="PROC-001",
        procedure_description="Low cost procedure",
        estimated_cost=499.0,
        provider_id="PROV-001",
    )
    
    response = agent.authorize(request)
    
    assert response.decision == "auto_approved"
    assert response.estimated_cost == 499.0


def test_supervisor_review_at_threshold():
    """Test supervisor review for $500 procedure."""
    agent = InsuranceAuthorizationAgent()
    
    request = AuthorizationRequest(
        patient_id="PAT-002",
        procedure_code="PROC-002",
        procedure_description="Medium cost procedure",
        estimated_cost=500.0,
        provider_id="PROV-001",
    )
    
    response = agent.authorize(request)
    
    assert response.decision == "supervisor_review"


def test_supervisor_review_at_upper_threshold():
    """Test supervisor review for $5000 procedure."""
    agent = InsuranceAuthorizationAgent()
    
    request = AuthorizationRequest(
        patient_id="PAT-003",
        procedure_code="PROC-003",
        procedure_description="High cost procedure",
        estimated_cost=5000.0,
        provider_id="PROV-001",
    )
    
    response = agent.authorize(request)
    
    assert response.decision == "supervisor_review"


def test_human_escalation_above_threshold():
    """Test human escalation for $5001 procedure."""
    agent = InsuranceAuthorizationAgent()
    
    request = AuthorizationRequest(
        patient_id="PAT-004",
        procedure_code="PROC-004",
        procedure_description="Very high cost procedure",
        estimated_cost=5001.0,
        provider_id="PROV-001",
    )
    
    response = agent.authorize(request)
    
    assert response.decision == "human_escalation"


def test_zero_cost_procedure():
    """Test edge case: $0 cost procedure."""
    agent = InsuranceAuthorizationAgent()
    
    request = AuthorizationRequest(
        patient_id="PAT-005",
        procedure_code="PROC-005",
        procedure_description="Free procedure",
        estimated_cost=0.0,
        provider_id="PROV-001",
    )
    
    response = agent.authorize(request)
    
    assert response.decision == "auto_approved"
    assert response.estimated_cost == 0.0


def test_policy_evaluation_included():
    """Test that policy evaluation is included in response."""
    agent = InsuranceAuthorizationAgent()
    
    request = AuthorizationRequest(
        patient_id="PAT-006",
        procedure_code="PROC-006",
        procedure_description="Test procedure",
        estimated_cost=1000.0,
        provider_id="PROV-001",
    )
    
    response = agent.authorize(request)
    
    assert response.policy_evaluation is not None
    assert isinstance(response.policy_evaluation, dict)
    assert "procedure_covered" in response.policy_evaluation
    assert "provider_in_network" in response.policy_evaluation
    assert "patient_eligible" in response.policy_evaluation
