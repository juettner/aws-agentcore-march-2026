"""Patient Eligibility Agent - screens patients against clinical trial criteria.

Uses Bedrock Knowledge Base for trial protocols and medical literature,
and AgentCore Gateway for EHR patient record retrieval.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

from medflow.shared.models.eligibility import (
    Citation,
    CriterionEvaluation,
    EligibilityRequest,
    EligibilityResponse,
)
from medflow.shared.models.patient import PatientRecord
from medflow.shared.utils.gateway_client import EHRGatewayClient
from medflow.shared.utils.knowledge_base_client import KnowledgeBaseClient

logger = logging.getLogger(__name__)

_REASONING_MODEL = os.environ.get(
    "ELIGIBILITY_REASONING_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
)


class PatientEligibilityAgent:
    """Screens patients against clinical trial inclusion/exclusion criteria.

    Retrieves patient records via Gateway, fetches trial criteria and supporting
    medical literature from Bedrock Knowledge Base, evaluates each criterion,
    and returns a structured eligibility report with citations.
    """

    def __init__(
        self,
        ehr_client: EHRGatewayClient,
        kb_client: KnowledgeBaseClient,
        region: str | None = None,
    ):
        self.ehr_client = ehr_client
        self.kb_client = kb_client
        self._bedrock = boto3.client(
            "bedrock-runtime",
            region_name=region or os.environ.get("AWS_REGION", "us-east-1"),
        )

    def evaluate(self, request: EligibilityRequest) -> EligibilityResponse:
        """Screen a patient against trial criteria.

        Args:
            request: EligibilityRequest with patientId and trialId.

        Returns:
            EligibilityResponse with per-criterion evaluations and citations.
        """
        logger.info(
            "Starting eligibility evaluation",
            extra={"patientId": request.patient_id, "trialId": request.trial_id},
        )

        # 6.2: Retrieve patient record via Gateway
        patient = self.ehr_client.get_patient_record(request.patient_id)

        # 6.1: Retrieve trial criteria from Knowledge Base
        protocol = self.kb_client.retrieve_trial_protocol(request.trial_id)

        evaluations: list[CriterionEvaluation] = []

        # Evaluate inclusion criteria
        for criterion in protocol.get("inclusionCriteria", []):
            evaluation = self._evaluate_criterion(
                criterion, patient, include=True
            )
            evaluations.append(evaluation)

        # Evaluate exclusion criteria
        for criterion in protocol.get("exclusionCriteria", []):
            evaluation = self._evaluate_criterion(
                criterion, patient, include=False
            )
            evaluations.append(evaluation)

        overall = self._determine_overall_eligibility(evaluations)

        logger.info(
            "Eligibility evaluation complete",
            extra={
                "patientId": request.patient_id,
                "trialId": request.trial_id,
                "overall": overall,
            },
        )

        return EligibilityResponse(
            patientId=request.patient_id,
            trialId=request.trial_id,
            overallEligibility=overall,
            criteriaEvaluations=evaluations,
            generatedAt=datetime.now(timezone.utc).isoformat(),
        )

    def _evaluate_criterion(
        self,
        criterion: dict[str, Any],
        patient: PatientRecord,
        include: bool,
    ) -> CriterionEvaluation:
        """Evaluate a single criterion against patient data with literature citations.

        For inclusion criteria a 'pass' means the patient meets the criterion.
        For exclusion criteria a 'pass' means the patient does NOT trigger it.
        """
        criterion_text = criterion["criterionText"]

        # 6.3: Semantic search for supporting medical literature
        raw_citations = self.kb_client.retrieve_medical_literature(
            f"{criterion_text} patient eligibility"
        )
        citations = [
            Citation(
                documentId=c["documentId"],
                title=c["title"],
                pageNumber=c.get("pageNumber"),
                relevanceScore=c["relevanceScore"],
            )
            for c in raw_citations
        ]

        result, reasoning = self._apply_criterion_logic(
            criterion_text, patient, include
        )

        return CriterionEvaluation(
            criterionId=criterion["criterionId"],
            criterionText=criterion_text,
            result=result,
            reasoning=reasoning,
            citations=citations,
        )

    def _apply_criterion_logic(
        self,
        criterion_text: str,
        patient: PatientRecord,
        include: bool,
    ) -> tuple[str, str]:
        """Use Claude to reason about whether the patient meets a criterion.

        Returns (result, reasoning) where result is 'pass', 'fail', or 'unknown'.
        """
        prompt = f"""You are a clinical trial eligibility screener.

Criterion: {criterion_text}
Type: {"inclusion" if include else "exclusion"}

Patient data:
- Age: {patient.demographics.age}
- Gender: {patient.demographics.gender}
- Diagnoses: {[d.description for d in patient.medical_history.diagnoses]}
- Allergies: {patient.medical_history.allergies}
- Comorbidities: {patient.medical_history.comorbidities}
- Medications: {[m.drug_name for m in patient.current_medications]}

Does the patient meet this criterion? Reply with JSON only:
{{"result": "pass" | "fail" | "unknown", "reasoning": "<one sentence>"}}"""

        response = self._bedrock.converse(
            modelId=_REASONING_MODEL,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
        )

        text = response["output"]["message"]["content"][0]["text"]
        parsed = json.loads(text)
        return parsed["result"], parsed["reasoning"]

    def _determine_overall_eligibility(
        self, evaluations: list[CriterionEvaluation]
    ) -> str:
        """Determine overall eligibility from individual criterion results."""
        if not evaluations:
            return "conditional"

        results = {e.result for e in evaluations}

        if "fail" in results:
            return "ineligible"
        if "unknown" in results:
            return "conditional"
        return "eligible"
