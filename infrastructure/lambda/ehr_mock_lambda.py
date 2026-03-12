"""Mock EHR API Lambda - returns sample patient records and lab results.
Used as an AgentCore Gateway target for demo purposes.
"""
import json
from datetime import datetime

PATIENTS = {
    "PAT-001": {
        "patientId": "PAT-001",
        "name": "Simon Schwob",
        "demographics": {"age": 45, "gender": "F", "ethnicity": "Caucasian"},
        "medicalHistory": {
            "diagnoses": [
                {"icd10Code": "E11", "description": "Type 2 Diabetes Mellitus", "diagnosisDate": "2018-06-01"},
                {"icd10Code": "I10", "description": "Hypertension", "diagnosisDate": "2019-03-15"},
                {"icd10Code": "E78.5", "description": "Hyperlipidemia", "diagnosisDate": "2020-01-10"},
            ],
            "allergies": ["Sulfonamides", "Penicillin"],
            "comorbidities": ["Hypertension", "Hyperlipidemia", "BMI 28.3"],
        },
        "currentMedications": [
            {"drugName": "Metformin",   "dosage": "1000mg", "frequency": "twice daily", "startDate": "2018-07-01"},
            {"drugName": "Lisinopril",  "dosage": "10mg",   "frequency": "once daily",  "startDate": "2019-04-01"},
            {"drugName": "Atorvastatin","dosage": "20mg",   "frequency": "once daily",  "startDate": "2020-02-01"},
        ],
        "vitalSigns": {"bloodPressure": "128/82", "heartRate": 72, "temperature": 98.6, "lastUpdated": "2026-03-01"},
        "labResults": [
            {"testName": "HbA1c",           "value": 7.8,  "unit": "%",       "referenceRange": "4.0-5.6", "testDate": "2026-03-01"},
            {"testName": "Fasting Glucose",  "value": 162,  "unit": "mg/dL",   "referenceRange": "70-100",  "testDate": "2026-03-01"},
            {"testName": "Creatinine",       "value": 1.1,  "unit": "mg/dL",   "referenceRange": "0.7-1.3", "testDate": "2026-03-01"},
            {"testName": "ALT",              "value": 28.0, "unit": "U/L",     "referenceRange": "7-56",    "testDate": "2026-03-01"},
            {"testName": "Total Cholesterol","value": 215,  "unit": "mg/dL",   "referenceRange": "<200",    "testDate": "2026-02-15"},
        ],
        "enrolledTrials": ["TRIAL-001"],
    },
    "PAT-002": {
        "patientId": "PAT-002",
        "name": "Matt Leising",
        "demographics": {"age": 62, "gender": "M", "ethnicity": "Asian"},
        "medicalHistory": {
            "diagnoses": [
                {"icd10Code": "C34.1", "description": "Non-Small Cell Lung Cancer, Stage IIIA", "diagnosisDate": "2025-11-01"},
                {"icd10Code": "J44.1", "description": "COPD", "diagnosisDate": "2017-05-20"},
                {"icd10Code": "I25.1", "description": "Coronary artery disease", "diagnosisDate": "2020-08-14"},
            ],
            "allergies": [],
            "comorbidities": ["COPD", "Coronary artery disease", "Former smoker"],
        },
        "currentMedications": [
            {"drugName": "Pembrolizumab","dosage": "200mg",   "frequency": "every 3 weeks","startDate": "2026-01-15"},
            {"drugName": "Carboplatin", "dosage": "AUC 5",   "frequency": "every 3 weeks","startDate": "2026-01-15"},
            {"drugName": "Tiotropium",  "dosage": "18mcg",   "frequency": "once daily",   "startDate": "2018-01-01"},
        ],
        "vitalSigns": {"bloodPressure": "134/88", "heartRate": 80, "temperature": 98.2, "lastUpdated": "2026-03-05"},
        "labResults": [
            {"testName": "WBC",         "value": 3.2,  "unit": "x10^9/L","referenceRange": "4.5-11.0",  "testDate": "2026-03-05"},
            {"testName": "Neutrophils", "value": 1.1,  "unit": "x10^9/L","referenceRange": "1.8-7.7",   "testDate": "2026-03-05"},
            {"testName": "Hemoglobin",  "value": 10.2, "unit": "g/dL",   "referenceRange": "13.5-17.5", "testDate": "2026-03-05"},
            {"testName": "Platelets",   "value": 145,  "unit": "x10^9/L","referenceRange": "150-400",   "testDate": "2026-03-05"},
            {"testName": "CEA",         "value": 8.5,  "unit": "ng/mL",  "referenceRange": "<3.0",      "testDate": "2026-02-28"},
        ],
        "enrolledTrials": ["TRIAL-002"],
    },
    "PAT-003": {
        "patientId": "PAT-003",
        "name": "Emily Rodriguez",
        "demographics": {"age": 34, "gender": "F", "ethnicity": "Hispanic"},
        "medicalHistory": {
            "diagnoses": [
                {"icd10Code": "M06.9", "description": "Rheumatoid Arthritis", "diagnosisDate": "2006-09-01"},
                {"icd10Code": "F32.9", "description": "Depression (managed)", "diagnosisDate": "2015-03-10"},
                {"icd10Code": "M85.8", "description": "Osteopenia", "diagnosisDate": "2022-07-22"},
            ],
            "allergies": ["Latex"],
            "comorbidities": ["Depression", "Osteopenia"],
        },
        "currentMedications": [
            {"drugName": "Adalimumab",  "dosage": "40mg", "frequency": "every 2 weeks","startDate": "2020-05-01"},
            {"drugName": "Methotrexate","dosage": "15mg", "frequency": "weekly",       "startDate": "2020-05-01"},
            {"drugName": "Folic acid",  "dosage": "1mg",  "frequency": "daily",        "startDate": "2020-05-01"},
        ],
        "vitalSigns": {"bloodPressure": "118/74", "heartRate": 68, "temperature": 98.4, "lastUpdated": "2026-03-03"},
        "labResults": [
            {"testName": "ESR",      "value": 42.0, "unit": "mm/hr",  "referenceRange": "0-20",  "testDate": "2026-03-03"},
            {"testName": "CRP",      "value": 2.8,  "unit": "mg/dL",  "referenceRange": "<0.5",  "testDate": "2026-03-03"},
            {"testName": "RF Factor","value": 85.0, "unit": "IU/mL",  "referenceRange": "<14",   "testDate": "2026-03-03"},
            {"testName": "ALT",      "value": 35.0, "unit": "U/L",    "referenceRange": "7-56",  "testDate": "2026-03-03"},
            {"testName": "WBC",      "value": 6.8,  "unit": "x10^9/L","referenceRange": "4.5-11.0","testDate": "2026-03-03"},
        ],
        "enrolledTrials": ["TRIAL-003"],
    },
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
    """Handle EHR API requests routed from AgentCore Gateway.

    AgentCore Gateway Lambda targets strip the tool name and send only the
    arguments as the event. Each tool is backed by a separate Lambda alias
    (e.g. arn:...:function:medflow-ehr-mock-api:get_patient_record), so we
    derive the tool name from the invoked function ARN qualifier.

    Falls back to toolName/name fields for direct invocation during testing.
    """
    try:
        # Derive tool name from alias in the invoked ARN (Gateway path),
        # or fall back to explicit fields (direct / test invocation path).
        arn_qualifier = context.invoked_function_arn.split(":")[-1] if context else ""
        tool_name = (arn_qualifier if arn_qualifier and not arn_qualifier.startswith("$")
                     else event.get("toolName")
                     or event.get("tool_name")
                     or event.get("name")
                     or "")
        # When invoked via Gateway alias the event IS the arguments dict.
        # When invoked directly (tests / fallback) it's wrapped in toolInput or arguments.
        tool_input = (event.get("toolInput")
                      or event.get("input")
                      or event.get("arguments")
                      or event)  # Gateway alias path: event = raw args

        if isinstance(tool_input, str):
            tool_input = json.loads(tool_input)

        # AgentCore Gateway Lambda targets expect raw data returned directly,
        # not wrapped in API Gateway proxy format (statusCode/body).
        if tool_name == "get_patient_record":
            patient_id = tool_input.get("patientId", tool_input.get("patient_id"))
            patient = PATIENTS.get(patient_id)
            if patient:
                return patient
            return {"error": f"Patient {patient_id} not found"}

        elif tool_name == "get_lab_results":
            patient_id = tool_input.get("patientId", tool_input.get("patient_id"))
            # Draw from the patient record's embedded labResults (authoritative source)
            patient = PATIENTS.get(patient_id, {})
            labs = patient.get("labResults", LAB_RESULTS.get(patient_id, []))
            return {"patientId": patient_id, "results": labs}

        elif tool_name == "get_adverse_events":
            patient_id = tool_input.get("patientId", tool_input.get("patient_id"))
            events = ADVERSE_EVENTS.get(patient_id, [])
            return {"patientId": patient_id, "adverseEvents": events}

        elif tool_name == "submit_insurance_auth":
            amount = tool_input.get("amount", 0)
            if amount < 500:
                decision = "AUTO_APPROVED"
            elif amount < 5000:
                decision = "PENDING_SUPERVISOR_REVIEW"
            else:
                decision = "ESCALATED_TO_MEDICAL_DIRECTOR"
            return {
                "authorizationId": f"AUTH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "decision": decision,
                "amount": amount,
                "timestamp": datetime.utcnow().isoformat()
            }

        elif tool_name == "list_patients":
            return {
                "patients": [
                    {"patientId": p["patientId"], "name": p["name"],
                     "diagnosis": p["medicalHistory"]["diagnoses"][0]["description"]}
                    for p in PATIENTS.values()
                ]
            }

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        return {"error": str(e)}
