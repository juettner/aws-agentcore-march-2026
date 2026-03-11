"""Orchestrator Agent - Top-level coordinator using Agent-as-Tool pattern.

Receives CoordinationRequests, routes to specialist agents, aggregates results,
and handles failures with logging and escalation.
"""

import logging
import time
from typing import Any

from medflow.agents.patient_eligibility import PatientEligibilityAgent
from medflow.agents.regulatory_report import RegulatoryReportAgent
from medflow.agents.insurance_auth import InsuranceAuthorizationAgent
from medflow.shared.models.coordination import (
    AgentError,
    AgentResult,
    CoordinationRequest,
    CoordinationResponse,
)
from medflow.shared.models.eligibility import EligibilityRequest
from medflow.shared.models.regulatory import RegulatoryReportRequest
from medflow.shared.models.authorization import AuthorizationRequest
from medflow.shared.utils.gateway_client import EHRGatewayClient
from medflow.shared.utils.knowledge_base_client import KnowledgeBaseClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent-as-Tool invocations
# Each function represents one specialist agent invoked as a tool.
# In production these call AgentCore Runtime via Strands Agent-as-Tool pattern.
# ---------------------------------------------------------------------------

def invoke_patient_eligibility_agent(patient_id: str, trial_id: str) -> dict[str, Any]:
    """Invoke Patient Eligibility Agent to screen a patient against trial criteria."""
    ehr_client = EHRGatewayClient()
    kb_client = KnowledgeBaseClient()
    agent = PatientEligibilityAgent(ehr_client, kb_client)
    
    request = EligibilityRequest(patient_id=patient_id, trial_id=trial_id)
    response = agent.evaluate(request)
    
    return {
        "patientId": response.patientId,
        "trialId": response.trialId,
        "overallEligibility": response.overallEligibility,
        "criteriaEvaluations": [
            {
                "criterionId": e.criterionId,
                "criterionText": e.criterionText,
                "result": e.result,
                "reasoning": e.reasoning,
                "citations": [
                    {
                        "documentId": c.documentId,
                        "title": c.title,
                        "pageNumber": c.pageNumber,
                        "relevanceScore": c.relevanceScore,
                    }
                    for c in e.citations
                ],
            }
            for e in response.criteriaEvaluations
        ],
        "generatedAt": response.generatedAt,
    }


def invoke_adverse_event_monitor(patient_id: str, symptoms: list[str]) -> dict[str, Any]:
    """Invoke Adverse Event Monitor to evaluate reported symptoms."""
    raise NotImplementedError("Adverse Event Monitor not yet implemented")


def invoke_regulatory_report_agent(
    report_type: str, trial_id: str, date_range: dict[str, str]
) -> dict[str, Any]:
    """Invoke Regulatory Report Agent to generate a compliance report."""
    agent = RegulatoryReportAgent()
    
    request = RegulatoryReportRequest(
        report_type=report_type,
        trial_id=trial_id,
        start_date=date_range["startDate"],
        end_date=date_range["endDate"],
    )
    response = agent.generate(request)
    
    return {
        "reportId": response.report_id,
        "reportType": response.report_type,
        "trialId": response.trial_id,
        "format": response.format,
        "pdfUrl": response.pdf_url,
        "sections": response.sections,
        "missingElements": response.missing_elements,
        "generatedAt": response.generated_at,
    }


def invoke_insurance_authorization_agent(
    procedure_code: str, cost: float, patient_id: str
) -> dict[str, Any]:
    """Invoke Insurance Authorization Agent to process an authorization request."""
    agent = InsuranceAuthorizationAgent()
    
    request = AuthorizationRequest(
        patient_id=patient_id,
        procedure_code=procedure_code,
        procedure_description=f"Procedure {procedure_code}",
        estimated_cost=cost,
        provider_id="PROV-001",
    )
    response = agent.authorize(request)
    
    return {
        "authorizationId": response.authorization_id,
        "patientId": response.patient_id,
        "procedureCode": response.procedure_code,
        "decision": response.decision,
        "estimatedCost": response.estimated_cost,
        "policyEvaluation": response.policy_evaluation,
        "generatedAt": response.generated_at,
    }


def invoke_patient_communication_agent(
    patient_id: str, check_in_type: str
) -> dict[str, Any]:
    """Invoke Patient Communication Agent to conduct a patient check-in."""
    raise NotImplementedError("Patient Communication Agent not yet implemented")


def invoke_trial_coordinator_agent(
    patient_ids: list[str], scheduling_constraints: dict[str, Any]
) -> dict[str, Any]:
    """Invoke Trial Coordinator Agent to schedule multiple patients."""
    raise NotImplementedError("Trial Coordinator Agent not yet implemented")


# ---------------------------------------------------------------------------
# Request routing
# ---------------------------------------------------------------------------

_REQUEST_TYPE_TO_AGENT = {
    "patient_screening": "PatientEligibilityAgent",
    "adverse_event_check": "AdverseEventMonitor",
    "regulatory_report": "RegulatoryReportAgent",
    "insurance_auth": "InsuranceAuthorizationAgent",
    "patient_checkin": "PatientCommunicationAgent",
    "trial_scheduling": "TrialCoordinatorAgent",
}


def _invoke_agent(request: CoordinationRequest) -> tuple[Any, str]:
    """Route request to the appropriate specialist agent and return (result, agent_name)."""
    p = request.payload
    rt = request.request_type

    if rt == "patient_screening":
        return invoke_patient_eligibility_agent(p["patientId"], p["trialId"]), _REQUEST_TYPE_TO_AGENT[rt]
    elif rt == "adverse_event_check":
        return invoke_adverse_event_monitor(p["patientId"], p["symptoms"]), _REQUEST_TYPE_TO_AGENT[rt]
    elif rt == "regulatory_report":
        return invoke_regulatory_report_agent(p["reportType"], p["trialId"], p["dateRange"]), _REQUEST_TYPE_TO_AGENT[rt]
    elif rt == "insurance_auth":
        return invoke_insurance_authorization_agent(p["procedureCode"], p["cost"], p["patientId"]), _REQUEST_TYPE_TO_AGENT[rt]
    elif rt == "patient_checkin":
        return invoke_patient_communication_agent(p["patientId"], p["checkInType"]), _REQUEST_TYPE_TO_AGENT[rt]
    elif rt == "trial_scheduling":
        return invoke_trial_coordinator_agent(p["patientIds"], p["schedulingConstraints"]), _REQUEST_TYPE_TO_AGENT[rt]
    else:
        raise ValueError(f"Unknown request type: {rt}")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class OrchestratorAgent:
    """Top-level coordinator that delegates to specialist agents via Agent-as-Tool pattern."""

    def coordinate(self, request: CoordinationRequest) -> CoordinationResponse:
        """Process a coordination request by routing to the appropriate specialist agent.

        Args:
            request: Parsed CoordinationRequest with type, priority, and payload.

        Returns:
            CoordinationResponse with aggregated results or error details.
        """
        logger.info(
            "Received coordination request",
            extra={
                "requestId": request.request_id,
                "requestType": request.request_type,
                "priority": request.priority,
                "userId": request.requester.user_id,
            },
        )

        results: list[AgentResult] = []
        errors: list[AgentError] = []

        agent_name = _REQUEST_TYPE_TO_AGENT.get(request.request_type, "UnknownAgent")
        start = time.monotonic()

        try:
            agent_result, agent_name = _invoke_agent(request)
            execution_time = time.monotonic() - start

            results.append(AgentResult(
                agentName=agent_name,
                agentResult=agent_result,
                executionTime=execution_time,
            ))

            logger.info(
                "Agent completed successfully",
                extra={"requestId": request.request_id, "agentName": agent_name},
            )

        except Exception as exc:
            execution_time = time.monotonic() - start

            logger.error(
                "Agent invocation failed",
                extra={
                    "requestId": request.request_id,
                    "agentName": agent_name,
                    "error": str(exc),
                },
            )

            errors.append(AgentError(
                agentName=agent_name,
                errorMessage=str(exc),
                retryAttempts=0,
            ))

        status = _determine_status(results, errors)

        escalation_reason = None
        if status == "escalated":
            escalation_reason = f"Agent {agent_name} failed and requires human intervention"

        response = CoordinationResponse(
            requestId=request.request_id,
            status=status,
            results=results,
            errors=errors if errors else None,
            escalationReason=escalation_reason,
        )

        logger.info(
            "Coordination complete",
            extra={"requestId": request.request_id, "status": status},
        )

        return response


def _determine_status(
    results: list[AgentResult], errors: list[AgentError]
) -> str:
    """Determine overall coordination status from results and errors."""
    if errors and not results:
        return "escalated"
    if errors and results:
        return "partial"
    return "completed"
