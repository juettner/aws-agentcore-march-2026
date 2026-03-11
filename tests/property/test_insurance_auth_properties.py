"""Property-based tests for Insurance Authorization Agent."""

from hypothesis import given, strategies as st

from medflow.agents.insurance_auth import InsuranceAuthorizationAgent
from medflow.shared.models.authorization import AuthorizationRequest


@given(cost=st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False))
def test_property_cost_based_routing(cost):
    """Property 13: Authorization Cost-Based Routing.
    
    For any insurance authorization request:
    - If cost < $500, decision should be 'auto_approved'
    - If $500 <= cost <= $5000, decision should be 'supervisor_review'
    - If cost > $5000, decision should be 'human_escalation'
    """
    agent = InsuranceAuthorizationAgent()
    
    request = AuthorizationRequest(
        patient_id="PAT-001",
        procedure_code="PROC-001",
        procedure_description="Test procedure",
        estimated_cost=cost,
        provider_id="PROV-001",
    )
    
    response = agent.authorize(request)
    
    if cost < 500:
        assert response.decision == "auto_approved"
    elif cost <= 5000:
        assert response.decision == "supervisor_review"
    else:
        assert response.decision == "human_escalation"


@given(
    cost=st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False)
)
def test_property_policy_enforcement(cost):
    """Property 15: Authorization Policy Enforcement.
    
    For any authorization request, the agent should evaluate policies
    and include the evaluation results in the response.
    """
    agent = InsuranceAuthorizationAgent()
    
    request = AuthorizationRequest(
        patient_id="PAT-001",
        procedure_code="PROC-001",
        procedure_description="Test procedure",
        estimated_cost=cost,
        provider_id="PROV-001",
    )
    
    response = agent.authorize(request)
    
    # Policy evaluation should be present
    assert response.policy_evaluation is not None
    assert isinstance(response.policy_evaluation, dict)
    
    # Should contain expected policy checks
    assert "procedure_covered" in response.policy_evaluation
    assert "provider_in_network" in response.policy_evaluation
    assert "patient_eligible" in response.policy_evaluation
