"""Patient Eligibility Agent — AgentCore Runtime entrypoint.

Deploy with:
    agentcore configure --entrypoint agents/patient_eligibility/runtime_agent.py
    agentcore launch

Invoke:
    agentcore invoke '{"patient_id": "PAT-001", "trial_id": "TRIAL-001"}'

Or from demo/run_demo.py via invoke_agent_runtime().
"""

import json
import logging
import os
from datetime import datetime, timezone

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from medflow.agents.patient_eligibility.agent import PatientEligibilityAgent
from medflow.shared.models.eligibility import EligibilityRequest
from medflow.shared.utils.gateway_client import EHRGatewayClient
from medflow.shared.utils.knowledge_base_client import KnowledgeBaseClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from medflow.shared.utils.cloudwatch_logging import setup_cloudwatch_logging
setup_cloudwatch_logging()

app = BedrockAgentCoreApp()

# Initialise clients once per container lifetime, not per invocation
_ehr_client = EHRGatewayClient()
_kb_client = KnowledgeBaseClient()
_agent = PatientEligibilityAgent(ehr_client=_ehr_client, kb_client=_kb_client)


@app.entrypoint
def invoke(payload: dict, context) -> dict:
    """Screen a patient against a clinical trial's eligibility criteria.

    Expected payload:
        {
            "patient_id": "PAT-001",   # or "patientId"
            "trial_id":   "TRIAL-001"  # or "trialId"
        }

    Returns a JSON-serialisable dict of EligibilityResponse fields.
    """
    patient_id = payload.get("patient_id") or payload.get("patientId")
    trial_id   = payload.get("trial_id")   or payload.get("trialId")

    if not patient_id or not trial_id:
        return {
            "error": "Missing required fields: patient_id and trial_id",
            "received": list(payload.keys()),
        }

    logger.info("Evaluating eligibility", extra={"patientId": patient_id, "trialId": trial_id})

    request = EligibilityRequest(
        patientId=patient_id,
        trialId=trial_id,
        requestTimestamp=datetime.now(timezone.utc).isoformat(),
    )

    response = _agent.evaluate(request)
    return response.model_dump(by_alias=True)


if __name__ == "__main__":
    app.run()
