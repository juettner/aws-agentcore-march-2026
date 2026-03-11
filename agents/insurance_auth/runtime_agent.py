"""Insurance Authorization Agent — AgentCore Runtime entrypoint.

Deploy with:
    agentcore configure --entrypoint agents/insurance_auth/runtime_agent.py --name medflow_insurance_auth ...
    agentcore launch

Invoke:
    agentcore invoke '{
        "patient_id": "PAT-001",
        "procedure_code": "CPT-80053",
        "procedure_description": "Routine lab work",
        "estimated_cost": 250,
        "provider_id": "PROV-001"
    }'
"""

import dataclasses
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from medflow.agents.insurance_auth.agent import InsuranceAuthorizationAgent
from medflow.shared.models.authorization import AuthorizationRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

_agent = InsuranceAuthorizationAgent()


@app.entrypoint
def invoke(payload: dict, context) -> dict:
    """Process an insurance authorization request through Cedar policies.

    Expected payload:
        {
            "patient_id":             "PAT-001",
            "procedure_code":         "CPT-80053",
            "procedure_description":  "Routine lab work",
            "estimated_cost":         250,
            "provider_id":            "PROV-001"   # optional, defaults to PROV-001
        }
    """
    patient_id            = payload.get("patient_id")
    procedure_code        = payload.get("procedure_code")
    procedure_description = payload.get("procedure_description", "")
    estimated_cost        = payload.get("estimated_cost")
    provider_id           = payload.get("provider_id", "PROV-001")

    if not patient_id or not procedure_code or estimated_cost is None:
        return {"error": "Missing required fields: patient_id, procedure_code, estimated_cost"}

    logger.info(
        "Processing authorization",
        extra={"patientId": patient_id, "procedureCode": procedure_code, "cost": estimated_cost},
    )

    request = AuthorizationRequest(
        patient_id=patient_id,
        procedure_code=procedure_code,
        procedure_description=procedure_description,
        estimated_cost=float(estimated_cost),
        provider_id=provider_id,
    )

    response = _agent.authorize(request)
    return dataclasses.asdict(response)


if __name__ == "__main__":
    app.run()
