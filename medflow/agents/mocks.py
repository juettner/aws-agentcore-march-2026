"""Mock specialist agents for integration testing.

Each mock returns a minimal but structurally valid response matching the
real agent's output interface, without any external dependencies.
"""

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mock_patient_eligibility_agent(patient_id: str, trial_id: str) -> dict:
    return {
        "patientId": patient_id,
        "trialId": trial_id,
        "overallEligibility": "eligible",
        "criteriaEvaluations": [
            {
                "criterionId": "C001",
                "criterionText": "Age 18-65",
                "result": "pass",
                "reasoning": "Patient age within range",
                "citations": [
                    {
                        "documentId": "DOC-001",
                        "title": "Trial Protocol v1.0",
                        "pageNumber": 12,
                        "relevanceScore": 0.95,
                    }
                ],
            }
        ],
        "generatedAt": _now(),
    }


def mock_adverse_event_monitor(patient_id: str, symptoms: list[str]) -> dict:
    return {
        "patientId": patient_id,
        "detectedEvents": [
            {
                "eventId": "EVT-001",
                "eventType": "Nausea",
                "severityGrade": 2,
                "confidence": 0.82,
                "relatedSymptoms": symptoms,
                "similarHistoricalCases": [
                    {"caseId": "CASE-001", "similarity": 0.88, "outcome": "resolved"}
                ],
            }
        ],
        "alertGenerated": False,
        "recommendedActions": ["Monitor patient", "Follow up in 48 hours"],
    }


def mock_regulatory_report_agent(
    report_type: str, trial_id: str, date_range: dict
) -> dict:
    return {
        "reportId": f"RPT-{trial_id}-001",
        "reportType": report_type,
        "pdfUrl": f"s3://medflow-reports/{trial_id}/report-001.pdf",
        "completenessStatus": "complete",
        "missingElements": [],
        "generatedAt": _now(),
        "validationErrors": [],
    }


def mock_insurance_authorization_agent(
    procedure_code: str, cost: float, patient_id: str
) -> dict:
    decision = "auto_approved" if cost < 500 else "supervisor_review"
    return {
        "authorizationId": f"AUTH-{patient_id}-001",
        "decision": decision,
        "approvalAmount": cost,
        "routingDestination": "auto" if decision == "auto_approved" else "supervisor_queue",
        "policyEvaluations": [
            {
                "policyId": "POL-001",
                "policyRule": "cost < 500 => auto_approve",
                "evaluation": "allow" if decision == "auto_approved" else "deny",
            }
        ],
        "externalApiCalls": [
            {"provider": "InsuranceProviderA", "status": "success", "responseTime": 120}
        ],
    }


def mock_patient_communication_agent(patient_id: str, check_in_type: str) -> dict:
    return {
        "patientId": patient_id,
        "callDuration": 180,
        "conversationSummary": {
            "symptomsReported": ["mild fatigue"],
            "medicationAdherence": "compliant",
            "concernsRaised": [],
            "escalationTriggered": False,
        },
        "transcript": "Agent: How are you feeling? Patient: I have mild fatigue.",
        "audioRecordingUrl": f"s3://medflow-recordings/{patient_id}/checkin-001.mp3",
        "generatedAt": _now(),
    }


def mock_trial_coordinator_agent(
    patient_ids: list[str], scheduling_constraints: dict
) -> dict:
    schedule = [
        {
            "patientId": pid,
            "appointmentSlot": f"2024-06-{10 + i:02d}T09:00:00Z",
            "location": "Clinic A",
            "status": "scheduled",
        }
        for i, pid in enumerate(patient_ids)
    ]
    return {
        "scheduledPatients": len(patient_ids),
        "schedule": schedule,
        "conflicts": [],
        "generatedAt": _now(),
    }
