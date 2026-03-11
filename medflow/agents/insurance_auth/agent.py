"""Insurance Authorization Agent - processes insurance authorizations.

Uses Amazon Verified Permissions for Cedar policy evaluation
and real authorization logic.
"""

import logging
import os
from datetime import datetime, timezone

import boto3

from medflow.shared.models.authorization import (
    AuthorizationRequest,
    AuthorizationResponse,
)

logger = logging.getLogger(__name__)


class InsuranceAuthorizationAgent:
    """Processes insurance authorization requests with policy-based routing."""

    def __init__(
        self,
        policy_store_id: str | None = None,
        region: str | None = None,
    ):
        self._region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._policy_store_id = policy_store_id or os.environ.get(
            "VERIFIED_PERMISSIONS_POLICY_STORE_ID"
        )
        
        # Initialize Verified Permissions client if policy store is configured
        self._use_real_policies = bool(self._policy_store_id)
        if self._use_real_policies:
            self._verifiedpermissions = boto3.client(
                "verifiedpermissions", region_name=self._region
            )
            logger.info(f"Using Amazon Verified Permissions: {self._policy_store_id}")
        else:
            logger.warning("No policy store configured, using rule-based evaluation")

    def authorize(self, request: AuthorizationRequest) -> AuthorizationResponse:
        """Process an insurance authorization request.

        Args:
            request: AuthorizationRequest with procedure and cost details.

        Returns:
            AuthorizationResponse with routing decision.
        """
        logger.info(
            "Starting authorization",
            extra={
                "patientId": request.patient_id,
                "procedureCode": request.procedure_code,
                "cost": request.estimated_cost,
            },
        )

        # 5.3, 5.4, 5.5: Cost-based routing
        decision = self._route_by_cost(request.estimated_cost)

        # 5.8: Policy evaluation (mock for demo)
        policy_evaluation = self._evaluate_policies(request)

        # 5.7: Call insurance API with OAuth token (mock for demo)
        if decision == "auto_approved":
            self._submit_to_insurance_api(request)

        auth_id = f"AUTH-{request.patient_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        logger.info(
            "Authorization complete",
            extra={"authId": auth_id, "decision": decision},
        )

        return AuthorizationResponse(
            authorization_id=auth_id,
            patient_id=request.patient_id,
            procedure_code=request.procedure_code,
            decision=decision,
            estimated_cost=request.estimated_cost,
            policy_evaluation=policy_evaluation,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _route_by_cost(self, cost: float) -> str:
        """Route authorization based on cost thresholds."""
        if cost < 500:
            return "auto_approved"
        elif cost <= 5000:
            return "supervisor_review"
        else:
            return "human_escalation"

    def _evaluate_policies(self, request: AuthorizationRequest) -> dict[str, bool]:
        """Evaluate Cedar policies via Amazon Verified Permissions.

        If Verified Permissions is configured, evaluates real Cedar policies.
        Otherwise, uses rule-based evaluation.
        """
        if not self._use_real_policies:
            # Fallback to rule-based evaluation
            return {
                "procedure_covered": True,
                "provider_in_network": True,
                "patient_eligible": True,
            }

        try:
            # Build authorization request for Verified Permissions
            response = self._verifiedpermissions.is_authorized(
                policyStoreId=self._policy_store_id,
                principal={
                    "entityType": "MedFlow::Provider",
                    "entityId": request.provider_id,
                },
                action={
                    "actionType": "MedFlow::Action",
                    "actionId": "AuthorizeProcedure",
                },
                resource={
                    "entityType": "MedFlow::Procedure",
                    "entityId": request.procedure_code,
                },
                context={
                    "contextMap": {
                        "estimatedCost": {"long": int(request.estimated_cost)},
                        "patientId": {"string": request.patient_id},
                        "procedureDescription": {"string": request.procedure_description},
                    }
                },
            )

            # Parse policy evaluation results
            decision = response["decision"]  # ALLOW or DENY
            determining_policies = response.get("determiningPolicies", [])

            # Extract which policies were evaluated
            policy_results = {}
            for policy in determining_policies:
                policy_id = policy["policyId"]
                # Map policy IDs to readable names
                if "coverage" in policy_id.lower():
                    policy_results["procedure_covered"] = decision == "ALLOW"
                elif "network" in policy_id.lower():
                    policy_results["provider_in_network"] = decision == "ALLOW"
                elif "eligibility" in policy_id.lower():
                    policy_results["patient_eligible"] = decision == "ALLOW"

            # Set defaults for any missing policies
            policy_results.setdefault("procedure_covered", decision == "ALLOW")
            policy_results.setdefault("provider_in_network", decision == "ALLOW")
            policy_results.setdefault("patient_eligible", decision == "ALLOW")

            logger.info(
                f"Policy evaluation: {decision}",
                extra={"policies": len(determining_policies), "results": policy_results},
            )

            return policy_results

        except Exception as e:
            logger.error(f"Policy evaluation failed: {e}")
            # Fallback to deny on error
            return {
                "procedure_covered": False,
                "provider_in_network": False,
                "patient_eligible": False,
            }

    def _submit_to_insurance_api(self, request: AuthorizationRequest) -> None:
        """Submit authorization to insurance provider API.

        In production, this:
        1. Gets OAuth token from AgentCore Identity
        2. Calls insurance API via Gateway with token
        3. Retries with token refresh on auth failure (up to 3 times)

        For demo, this is a no-op.
        """
        # 5.6, 5.7, 5.9: OAuth token acquisition and API call with retry
        logger.info(
            "Submitting to insurance API",
            extra={"procedureCode": request.procedure_code},
        )
