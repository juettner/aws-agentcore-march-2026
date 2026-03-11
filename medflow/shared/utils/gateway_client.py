"""AgentCore Gateway client wrapper for MCP-transformed REST APIs.

This module provides typed Python interfaces for calling REST APIs that have been
transformed into MCP-compatible tools by AgentCore Gateway.

Uses AWS IAM SigV4 authentication since the gateway is configured with AWS_IAM auth.
"""

import json
import os
import logging
from typing import List, Optional, Dict, Any

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
import httpx
from pydantic import ValidationError

from medflow.shared.models.patient import PatientRecord, LabResult

logger = logging.getLogger(__name__)


class GatewayClientError(Exception):
    """Base exception for Gateway client errors."""
    pass


class GatewayAuthenticationError(GatewayClientError):
    """Raised when authentication with Gateway fails."""
    pass


class GatewayAPIError(GatewayClientError):
    """Raised when the underlying API returns an error."""
    pass


class EHRGatewayClient:
    """Client for EHR API tools transformed by AgentCore Gateway.

    This client provides typed interfaces for the following MCP tools:
    - get_patient_record: Retrieve complete patient medical record
    - get_lab_results: Retrieve patient laboratory test results
    - get_adverse_events: Retrieve patient adverse events
    - list_patients: List all patients in the system

    Uses AWS IAM SigV4 authentication with the AgentCore Gateway.
    """

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        region: Optional[str] = None,
        timeout: int = 30,
    ):
        """Initialize EHR Gateway client.

        Args:
            gateway_url: Gateway MCP endpoint URL. If None, reads from
                AGENTCORE_GATEWAY_URL environment variable.
            region: AWS region. If None, reads from AWS_REGION env var.
            timeout: Request timeout in seconds.
        """
        self.gateway_url = gateway_url or os.getenv("AGENTCORE_GATEWAY_URL", "")
        self.region = region or os.getenv("AWS_REGION", "us-west-2")
        self.timeout = timeout

        # Get AWS credentials for SigV4 signing
        session = boto3.Session(region_name=self.region)
        self._credentials = session.get_credentials()
        if not self._credentials:
            raise GatewayClientError("AWS credentials not available for SigV4 signing.")
        self._credentials = self._credentials.get_frozen_credentials()

        self._client = httpx.Client(timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._client.close()

    def _sign_request(self, method: str, url: str, body: str) -> Dict[str, str]:
        """Sign a request using AWS SigV4.

        Returns headers dict with Authorization, x-amz-date, etc.
        """
        request = AWSRequest(method=method, url=url, data=body, headers={
            "Content-Type": "application/json",
            "Host": url.split("//")[1].split("/")[0],
        })
        SigV4Auth(self._credentials, "bedrock-agentcore", self.region).add_auth(request)
        return dict(request.headers)

    def _call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool through AgentCore Gateway.

        Uses the MCP protocol: POST to gateway URL with JSON-RPC style request.

        Args:
            tool_name: Name of the MCP tool to invoke
            parameters: Tool parameters as dictionary

        Returns:
            Tool response as dictionary
        """
        body = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": parameters,
            },
            "id": 1,
        })

        try:
            signed_headers = self._sign_request("POST", self.gateway_url, body)
            response = self._client.post(
                self.gateway_url,
                content=body,
                headers=signed_headers,
            )

            if response.status_code == 401:
                raise GatewayAuthenticationError(
                    f"SigV4 authentication failed for tool '{tool_name}'"
                )

            if response.status_code == 403:
                raise GatewayAuthenticationError(
                    f"Authorization denied for tool '{tool_name}'"
                )

            if response.status_code >= 400:
                raise GatewayAPIError(
                    f"API error calling tool '{tool_name}': "
                    f"Status {response.status_code}, Detail: {response.text}"
                )

            result = response.json()
            # MCP response format: {"jsonrpc": "2.0", "result": {...}, "id": 1}
            if "result" in result:
                content = result["result"]
                # If content is a list with text content, parse the JSON
                if isinstance(content, dict) and "content" in content:
                    for item in content["content"]:
                        if item.get("type") == "text":
                            return json.loads(item["text"])
                return content
            elif "error" in result:
                raise GatewayAPIError(
                    f"MCP error for tool '{tool_name}': {result['error']}"
                )
            return result

        except httpx.TimeoutException as e:
            raise GatewayClientError(f"Timeout calling tool '{tool_name}': {e}")
        except httpx.RequestError as e:
            raise GatewayClientError(f"Request error calling tool '{tool_name}': {e}")

    def get_patient_record(self, patient_id: str) -> PatientRecord:
        """Retrieve complete patient medical record via MCP tool."""
        try:
            response_data = self._call_tool(
                tool_name="get_patient_record",
                parameters={"patientId": patient_id},
            )
            return PatientRecord(**response_data)
        except ValidationError as e:
            raise GatewayClientError(f"Failed to parse patient record: {e}")

    def get_lab_results(
        self,
        patient_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[LabResult]:
        """Retrieve patient laboratory test results via MCP tool."""
        parameters: Dict[str, Any] = {"patientId": patient_id}
        if start_date:
            parameters["startDate"] = start_date
        if end_date:
            parameters["endDate"] = end_date

        try:
            response_data = self._call_tool(
                tool_name="get_lab_results",
                parameters=parameters,
            )
            results = response_data.get("results", response_data) if isinstance(response_data, dict) else response_data
            if not isinstance(results, list):
                raise GatewayClientError(f"Expected list of lab results, got {type(results)}")
            return [LabResult(**item) for item in results]
        except ValidationError as e:
            raise GatewayClientError(f"Failed to parse lab results: {e}")

    def get_adverse_events(self, patient_id: str) -> List[Dict[str, Any]]:
        """Retrieve patient adverse events via MCP tool."""
        response_data = self._call_tool(
            tool_name="get_adverse_events",
            parameters={"patientId": patient_id},
        )
        return response_data.get("adverseEvents", []) if isinstance(response_data, dict) else response_data

    def list_patients(self) -> List[Dict[str, Any]]:
        """List all patients in the EHR system."""
        response_data = self._call_tool(
            tool_name="list_patients",
            parameters={},
        )
        return response_data.get("patients", []) if isinstance(response_data, dict) else response_data


class InsuranceGatewayClient:
    """Client for Insurance authorization via AgentCore Gateway.

    Uses the submit_insurance_auth MCP tool to process authorization requests
    through the Lambda-backed gateway target.
    """

    def __init__(
        self,
        gateway_url: Optional[str] = None,
        region: Optional[str] = None,
        timeout: int = 30,
    ):
        self._ehr_client = EHRGatewayClient(
            gateway_url=gateway_url,
            region=region,
            timeout=timeout,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._ehr_client.close()

    def submit_authorization_request(
        self,
        procedure_code: str,
        patient_id: str,
        estimated_cost: float,
        urgency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit insurance authorization request for procedure.

        Args:
            procedure_code: CPT or HCPCS procedure code
            patient_id: Patient identifier
            estimated_cost: Estimated procedure cost in USD
            urgency: Optional urgency level (routine, urgent, emergency)

        Returns:
            Authorization response with authorizationId, decision, amount.
        """
        parameters: Dict[str, Any] = {
            "patientId": patient_id,
            "procedureCode": procedure_code,
            "amount": estimated_cost,
            "description": f"Authorization for procedure {procedure_code}",
        }

        if urgency:
            if urgency not in ["routine", "urgent", "emergency"]:
                raise GatewayClientError(
                    f"Invalid urgency: {urgency}. Must be routine, urgent, or emergency"
                )
            parameters["urgency"] = urgency

        return self._ehr_client._call_tool(
            tool_name="submit_insurance_auth",
            parameters=parameters,
        )
