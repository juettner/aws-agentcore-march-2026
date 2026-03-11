"""Adverse Event Monitor — AgentCore Runtime entrypoint.

Deploy with:
    agentcore configure --entrypoint agents/adverse_event/runtime_agent.py --name medflow_adverse_event ...
    agentcore launch

Invoke:
    agentcore invoke '{
        "patient_id": "PAT-002",
        "symptoms": ["neutropenia", "fatigue"],
        "medications": ["carboplatin", "MF-5120"],
        "timeline": "Grade 3 Neutropenia on Day 14, ANC 850",
        "store_outcome": true
    }'
"""

import dataclasses
import logging
import os
from datetime import datetime

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from medflow.agents.adverse_event.agent import AdverseEventMonitor
from medflow.shared.models.adverse_event import AdverseEventCheckRequest
from medflow.shared.utils.memory_client import MemoryClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

_memory_client = MemoryClient()
_agent = AdverseEventMonitor(memory_client=_memory_client)


def _serializable(obj):
    """Recursively convert a dataclass dict, turning datetimes into ISO strings."""
    if isinstance(obj, dict):
        return {k: _serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serializable(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


@app.entrypoint
def invoke(payload: dict, context) -> dict:
    """Check and optionally store an adverse event.

    Expected payload:
        {
            "patient_id":    "PAT-002",
            "symptoms":      ["neutropenia", "fatigue"],
            "medications":   ["carboplatin", "MF-5120"],
            "timeline":      "Grade 3 on Day 14, ANC 850",
            "store_outcome": true          # optional, default false
        }
    """
    patient_id   = payload.get("patient_id")
    symptoms     = payload.get("symptoms", [])
    medications  = payload.get("medications", [])
    timeline     = payload.get("timeline", "")
    store        = payload.get("store_outcome", False)

    if not patient_id or not symptoms:
        return {"error": "Missing required fields: patient_id and symptoms"}

    logger.info("Checking adverse event", extra={"patientId": patient_id})

    request = AdverseEventCheckRequest(
        patient_id=patient_id,
        symptoms=symptoms,
        medications=medications,
        timeline=timeline,
        vital_signs=payload.get("vital_signs"),
    )

    response = _agent.check_adverse_event(request)

    if store:
        _agent.store_outcome(request, response.recommendation, response.severity_grade)
        logger.info("Episode stored in Memory", extra={"patientId": patient_id})

    return _serializable(dataclasses.asdict(response))


if __name__ == "__main__":
    app.run()
