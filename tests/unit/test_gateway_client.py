"""Unit tests for AgentCore Gateway client wrappers.

Tests cover:
- Successful API transformation (EHR and Insurance)
- Authentication handling (401/403 errors)
- Error response parsing (4xx/5xx errors)
- Timeout and request errors
"""

import pytest
from unittest.mock import MagicMock, patch
import httpx

from medflow.shared.utils.gateway_client import (
    EHRGatewayClient,
    InsuranceGatewayClient,
    GatewayAuthenticationError,
    GatewayAPIError,
    GatewayClientError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ehr_client():
    with patch("httpx.Client"):
        client = EHRGatewayClient(
            gateway_base_url="https://gateway.example.com",
            api_key="test-key"
        )
        yield client


@pytest.fixture
def insurance_client():
    with patch("httpx.Client"):
        client = InsuranceGatewayClient(
            gateway_base_url="https://gateway.example.com",
            api_key="test-key"
        )
        yield client


def _mock_response(status_code: int, json_data=None, text: str = ""):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = text
    response.json.return_value = json_data or {}
    return response


# ---------------------------------------------------------------------------
# EHRGatewayClient - successful API transformation
# ---------------------------------------------------------------------------

PATIENT_RECORD_DATA = {
    "patientId": "P001",
    "demographics": {"age": 45, "gender": "F"},
    "medicalHistory": {
        "diagnoses": [{"icd10Code": "E11.9", "description": "Type 2 diabetes", "diagnosisDate": "2020-01-01"}],
        "allergies": ["penicillin"],
        "comorbidities": []
    },
    "currentMedications": [{"drugName": "Metformin", "dosage": "500mg", "frequency": "twice daily", "startDate": "2020-01-15"}],
    "vitalSigns": {"bloodPressure": "120/80", "heartRate": 72, "lastUpdated": "2024-01-01"},
    "labResults": []
}

LAB_RESULTS_DATA = [
    {"testName": "HbA1c", "value": 7.2, "unit": "%", "referenceRange": "4.0-5.6", "testDate": "2024-01-01"}
]


def test_get_patient_record_success(ehr_client):
    ehr_client._client.post.return_value = _mock_response(200, PATIENT_RECORD_DATA)

    record = ehr_client.get_patient_record("P001")

    assert record.patient_id == "P001"
    assert record.demographics.age == 45
    ehr_client._client.post.assert_called_once_with(
        "/tools/invoke",
        json={"tool_name": "get_patient_record", "parameters": {"patientId": "P001"}}
    )


def test_get_lab_results_success(ehr_client):
    ehr_client._client.post.return_value = _mock_response(200, LAB_RESULTS_DATA)

    results = ehr_client.get_lab_results("P001", start_date="2024-01-01")

    assert len(results) == 1
    assert results[0].test_name == "HbA1c"
    ehr_client._client.post.assert_called_once_with(
        "/tools/invoke",
        json={"tool_name": "get_lab_results", "parameters": {"patientId": "P001", "startDate": "2024-01-01"}}
    )


# ---------------------------------------------------------------------------
# EHRGatewayClient - authentication handling
# ---------------------------------------------------------------------------

def test_get_patient_record_401_raises_auth_error(ehr_client):
    ehr_client._client.post.return_value = _mock_response(401)

    with pytest.raises(GatewayAuthenticationError):
        ehr_client.get_patient_record("P001")


def test_get_patient_record_403_raises_auth_error(ehr_client):
    ehr_client._client.post.return_value = _mock_response(403)

    with pytest.raises(GatewayAuthenticationError):
        ehr_client.get_patient_record("P001")


# ---------------------------------------------------------------------------
# EHRGatewayClient - error response parsing
# ---------------------------------------------------------------------------

def test_get_patient_record_500_raises_api_error(ehr_client):
    ehr_client._client.post.return_value = _mock_response(500, text="Internal Server Error")

    with pytest.raises(GatewayAPIError, match="Status 500"):
        ehr_client.get_patient_record("P001")


def test_get_lab_results_non_list_response_raises_error(ehr_client):
    ehr_client._client.post.return_value = _mock_response(200, {"unexpected": "object"})

    with pytest.raises(GatewayClientError, match="Expected list"):
        ehr_client.get_lab_results("P001")


def test_get_patient_record_timeout_raises_client_error(ehr_client):
    ehr_client._client.post.side_effect = httpx.TimeoutException("timed out")

    with pytest.raises(GatewayClientError, match="Timeout"):
        ehr_client.get_patient_record("P001")


# ---------------------------------------------------------------------------
# InsuranceGatewayClient - successful API transformation
# ---------------------------------------------------------------------------

AUTH_RESPONSE_DATA = {
    "authorizationId": "AUTH-123",
    "status": "approved",
    "approvalAmount": 450.0,
    "expirationDate": "2024-06-01"
}


def test_submit_authorization_request_success(insurance_client):
    insurance_client._client.post.return_value = _mock_response(200, AUTH_RESPONSE_DATA)

    result = insurance_client.submit_authorization_request(
        procedure_code="99213",
        patient_id="P001",
        estimated_cost=450.0,
        urgency="routine"
    )

    assert result["authorizationId"] == "AUTH-123"
    assert result["status"] == "approved"
    insurance_client._client.post.assert_called_once_with(
        "/tools/invoke",
        json={
            "tool_name": "submit_authorization_request",
            "parameters": {
                "procedureCode": "99213",
                "patientId": "P001",
                "estimatedCost": 450.0,
                "urgency": "routine"
            }
        }
    )


# ---------------------------------------------------------------------------
# InsuranceGatewayClient - authentication handling
# ---------------------------------------------------------------------------

def test_submit_authorization_401_raises_auth_error(insurance_client):
    insurance_client._client.post.return_value = _mock_response(401)

    with pytest.raises(GatewayAuthenticationError):
        insurance_client.submit_authorization_request("99213", "P001", 450.0)


def test_submit_authorization_403_raises_auth_error(insurance_client):
    insurance_client._client.post.return_value = _mock_response(403)

    with pytest.raises(GatewayAuthenticationError):
        insurance_client.submit_authorization_request("99213", "P001", 450.0)


# ---------------------------------------------------------------------------
# InsuranceGatewayClient - error response parsing
# ---------------------------------------------------------------------------

def test_submit_authorization_500_raises_api_error(insurance_client):
    insurance_client._client.post.return_value = _mock_response(500, text="Service Unavailable")

    with pytest.raises(GatewayAPIError, match="Status 500"):
        insurance_client.submit_authorization_request("99213", "P001", 450.0)


def test_submit_authorization_invalid_urgency_raises_error(insurance_client):
    with pytest.raises(GatewayClientError, match="Invalid urgency"):
        insurance_client.submit_authorization_request("99213", "P001", 450.0, urgency="critical")


def test_submit_authorization_request_error_raises_client_error(insurance_client):
    insurance_client._client.post.side_effect = httpx.RequestError("connection refused")

    with pytest.raises(GatewayClientError, match="Request error"):
        insurance_client.submit_authorization_request("99213", "P001", 450.0)


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------

def test_ehr_client_missing_url_raises_error():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(GatewayClientError, match="Gateway base URL"):
            EHRGatewayClient(api_key="test-key")


def test_ehr_client_missing_api_key_raises_error():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(GatewayClientError, match="Gateway API key"):
            EHRGatewayClient(gateway_base_url="https://gateway.example.com")
