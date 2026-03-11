"""Mock EHR API Lambda - returns sample patient records and lab results.
Used as an AgentCore Gateway target for demo purposes.
"""
import json
from datetime import datetime

PATIENTS = {
    "PAT-001": {
        "patientId": "PAT-001",
        "name": "Sarah Johnson",
        "age": 45,
        "gender": "Female",
        "diagnosis": "Type 2 Diabetes Mellitus",
        "enrolledTrials": ["TRIAL-001"],
        "medicalHistory": [
            "Hypertension (diagnosed 2019)",
            "Hyperlipidemia (diagnosed 2020)",
            "BMI 28.3"
        ],
        "currentMedications": [
            {"name": "Metformin", "dose": "1000mg", "frequency": "twice daily"},
            {"name": "Lisinopril", "dose": "10mg", "frequency": "once daily"},
            {"name": "Atorvastatin", "dose": "20mg", "frequency": "once daily"}
        ],
        "allergies": ["Sulfonamides", "Penicillin"]
    },
    "PAT-002": {
        "patientId": "PAT-002",
        "name": "Michael Chen",
        "age": 62,
        "gender": "Male",
        "diagnosis": "Non-Small Cell Lung Cancer, Stage IIIA",
        "enrolledTrials": ["TRIAL-002"],
        "medicalHistory": [
            "Former smoker (quit 2018)",
            "COPD (diagnosed 2017)",
            "Coronary artery disease"
        ],
        "currentMedications": [
            {"name": "Pembrolizumab", "dose": "200mg", "frequency": "every 3 weeks"},
            {"name": "Carboplatin", "dose": "AUC 5", "frequency": "every 3 weeks"},
            {"name": "Tiotropium", "dose": "18mcg", "frequency": "once daily"}
        ],
        "allergies": []
    },
    "PAT-003": {
        "patientId": "PAT-003",
        "name": "Emily Rodriguez",
        "age": 34,
        "gender": "Female",
        "diagnosis": "Rheumatoid Arthritis",
        "enrolledTrials": ["TRIAL-003"],
        "medicalHistory": [
            "Juvenile RA (diagnosed age 12)",
            "Depression (managed)",
            "Osteopenia"
        ],
        "currentMedications": [
            {"name": "Adalimumab", "dose": "40mg", "frequency": "every 2 weeks"},
            {"name": "Methotrexate", "dose": "15mg", "frequency": "weekly"},
            {"name": "Folic acid", "dose": "1mg", "frequency": "daily"}
        ],
        "allergies": ["Latex"]
    }
}

LAB_RESULTS = {
    "PAT-001": [
        {"testName": "HbA1c", "value": 7.8, "unit": "%", "referenceRange": "4.0-5.6", "status": "HIGH", "date": "2026-03-01"},
        {"testName": "Fasting Glucose", "value": 162, "unit": "mg/dL", "referenceRange": "70-100", "status": "HIGH", "date": "2026-03-01"},
        {"testName": "Creatinine", "value": 1.1, "unit": "mg/dL", "referenceRange": "0.7-1.3", "status": "NORMAL", "date": "2026-03-01"},
        {"testName": "ALT", "value": 28, "unit": "U/L", "referenceRange": "7-56", "status": "NORMAL", "date": "2026-03-01"},
        {"testName": "Total Cholesterol", "value": 215, "unit": "mg/dL", "referenceRange": "<200", "status": "HIGH", "date": "2026-02-15"}
    ],
    "PAT-002": [
        {"testName": "WBC", "value": 3.2, "unit": "x10^9/L", "referenceRange": "4.5-11.0", "status": "LOW", "date": "2026-03-05"},
        {"testName": "Neutrophils", "value": 1.1, "unit": "x10^9/L", "referenceRange": "1.8-7.7", "status": "LOW", "date": "2026-03-05"},
        {"testName": "Hemoglobin", "value": 10.2, "unit": "g/dL", "referenceRange": "13.5-17.5", "status": "LOW", "date": "2026-03-05"},
        {"testName": "Platelets", "value": 145, "unit": "x10^9/L", "referenceRange": "150-400", "status": "LOW", "date": "2026-03-05"},
        {"testName": "CEA", "value": 8.5, "unit": "ng/mL", "referenceRange": "<3.0", "status": "HIGH", "date": "2026-02-28"}
    ],
    "PAT-003": [
        {"testName": "ESR", "value": 42, "unit": "mm/hr", "referenceRange": "0-20", "status": "HIGH", "date": "2026-03-03"},
        {"testName": "CRP", "value": 2.8, "unit": "mg/dL", "referenceRange": "<0.5", "status": "HIGH", "date": "2026-03-03"},
        {"testName": "RF Factor", "value": 85, "unit": "IU/mL", "referenceRange": "<14", "status": "HIGH", "date": "2026-03-03"},
        {"testName": "ALT", "value": 35, "unit": "U/L", "referenceRange": "7-56", "status": "NORMAL", "date": "2026-03-03"},
        {"testName": "WBC", "value": 6.8, "unit": "x10^9/L", "referenceRange": "4.5-11.0", "status": "NORMAL", "date": "2026-03-03"}
    ]
}

ADVERSE_EVENTS = {
    "PAT-001": [
        {"eventId": "AE-001", "description": "Mild nausea", "severity": "MILD", "causalityAssessment": "POSSIBLE", "onsetDate": "2026-02-20", "status": "RESOLVED"},
        {"eventId": "AE-004", "description": "Elevated liver enzymes (Grade 1)", "severity": "MILD", "causalityAssessment": "PROBABLE", "onsetDate": "2026-03-02", "status": "ONGOING"}
    ],
    "PAT-002": [
        {"eventId": "AE-002", "description": "Grade 3 Neutropenia", "severity": "SEVERE", "causalityAssessment": "DEFINITE", "onsetDate": "2026-03-05", "status": "ONGOING"},
        {"eventId": "AE-003", "description": "Fatigue (Grade 2)", "severity": "MODERATE", "causalityAssessment": "PROBABLE", "onsetDate": "2026-02-25", "status": "ONGOING"}
    ],
    "PAT-003": [
        {"eventId": "AE-005", "description": "Injection site reaction", "severity": "MILD", "causalityAssessment": "DEFINITE", "onsetDate": "2026-03-01", "status": "RESOLVED"}
    ]
}


def lambda_handler(event, context):
    """Handle EHR API requests routed from AgentCore Gateway."""
    try:
        # Parse the tool name and input from the gateway invocation
        tool_name = event.get("toolName", event.get("tool_name", ""))
        tool_input = event.get("toolInput", event.get("input", {}))

        if isinstance(tool_input, str):
            tool_input = json.loads(tool_input)

        if tool_name == "get_patient_record":
            patient_id = tool_input.get("patientId", tool_input.get("patient_id"))
            patient = PATIENTS.get(patient_id)
            if patient:
                return {"statusCode": 200, "body": json.dumps(patient)}
            return {"statusCode": 404, "body": json.dumps({"error": f"Patient {patient_id} not found"})}

        elif tool_name == "get_lab_results":
            patient_id = tool_input.get("patientId", tool_input.get("patient_id"))
            labs = LAB_RESULTS.get(patient_id, [])
            return {"statusCode": 200, "body": json.dumps({"patientId": patient_id, "results": labs})}

        elif tool_name == "get_adverse_events":
            patient_id = tool_input.get("patientId", tool_input.get("patient_id"))
            events = ADVERSE_EVENTS.get(patient_id, [])
            return {"statusCode": 200, "body": json.dumps({"patientId": patient_id, "adverseEvents": events})}

        elif tool_name == "submit_insurance_auth":
            request_data = tool_input
            amount = request_data.get("amount", 0)
            if amount < 500:
                decision = "AUTO_APPROVED"
            elif amount < 5000:
                decision = "PENDING_SUPERVISOR_REVIEW"
            else:
                decision = "ESCALATED_TO_MEDICAL_DIRECTOR"
            return {"statusCode": 200, "body": json.dumps({
                "authorizationId": f"AUTH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "decision": decision,
                "amount": amount,
                "timestamp": datetime.utcnow().isoformat()
            })}

        elif tool_name == "list_patients":
            return {"statusCode": 200, "body": json.dumps({
                "patients": [{"patientId": p["patientId"], "name": p["name"], "diagnosis": p["diagnosis"]} for p in PATIENTS.values()]
            })}

        else:
            return {"statusCode": 400, "body": json.dumps({"error": f"Unknown tool: {tool_name}"})}

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
