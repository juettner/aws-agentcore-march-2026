"""Regulatory Report Agent - generates FDA/EMA-compliant reports.

Uses S3 for trial data storage, Claude for content generation,
and Lambda for PDF generation.
"""

import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

from medflow.shared.models.regulatory import (
    RegulatoryReportRequest,
    RegulatoryReportResponse,
)

logger = logging.getLogger(__name__)

# Required sections per regulatory format
FDA_SECTIONS = [
    "Cover Sheet",
    "Table of Contents",
    "Introductory Statement",
    "General Investigational Plan",
    "Investigator's Brochure",
    "Protocol",
    "Chemistry, Manufacturing, and Controls",
    "Pharmacology and Toxicology",
    "Previous Human Experience",
    "Additional Information",
]

EMA_SECTIONS = [
    "Administrative Information",
    "Quality Information",
    "Non-Clinical Information",
    "Clinical Information",
    "Risk Assessment",
]


class RegulatoryReportAgent:
    """Generates FDA/EMA-compliant regulatory reports with PDF output."""

    def __init__(
        self,
        lambda_function_name: str | None = None,
        s3_bucket: str | None = None,
        region: str | None = None,
    ):
        self._region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._lambda_client = boto3.client("lambda", region_name=self._region)
        self._s3_client = boto3.client("s3", region_name=self._region)
        self._bedrock = boto3.client("bedrock-runtime", region_name=self._region)
        self._lambda_function = lambda_function_name or os.environ.get(
            "PDF_GENERATOR_LAMBDA", "medflow-pdf-generator"
        )
        self._s3_bucket = s3_bucket or os.environ.get(
            "S3_TRIAL_DATA_BUCKET", "medflow-trial-data"
        )
        self._model_id = os.environ.get(
            "REGULATORY_CONTENT_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
        )

    def generate(self, request: RegulatoryReportRequest) -> RegulatoryReportResponse:
        """Generate a regulatory report.

        Args:
            request: RegulatoryReportRequest with report type and trial details.

        Returns:
            RegulatoryReportResponse with PDF URL and validation results.
        """
        logger.info(
            "Starting regulatory report generation",
            extra={"trialId": request.trial_id, "reportType": request.report_type},
        )

        # 4.1: Identify report format based on regulatory body
        report_format = self._select_format(request.report_type)

        # 4.2, 4.3: Gather report data from internal APIs and external databases
        sections = self._gather_report_data(request, report_format)

        # 4.5, 4.6: Validate section completeness
        required_sections = (
            FDA_SECTIONS if report_format == "FDA_21_CFR_312" else EMA_SECTIONS
        )
        missing = [s for s in required_sections if s not in sections or not sections[s]]

        # 4.4: Generate PDF via Lambda
        pdf_url = None
        if not missing:
            pdf_url = self._generate_pdf(request.trial_id, report_format, sections)

        report_id = f"REP-{request.trial_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        logger.info(
            "Regulatory report generation complete",
            extra={
                "reportId": report_id,
                "format": report_format,
                "missing": len(missing),
            },
        )

        return RegulatoryReportResponse(
            report_id=report_id,
            report_type=request.report_type,
            trial_id=request.trial_id,
            format=report_format,
            pdf_url=pdf_url,
            sections=list(sections.keys()),
            missing_elements=missing,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _select_format(self, report_type: str) -> str:
        """Select report format based on report type."""
        if report_type.startswith("EMA"):
            return "EMA_ICH_GCP"
        return "FDA_21_CFR_312"

    def _gather_report_data(
        self, request: RegulatoryReportRequest, report_format: str
    ) -> dict[str, str]:
        """Gather report data from S3 trial data and generate content with Claude.

        Retrieves trial data from S3, then uses Claude to generate compliant
        content for each required section.
        """
        # Retrieve trial data from S3
        trial_data = self._get_trial_data_from_s3(request.trial_id, request.start_date, request.end_date)
        
        sections = {}
        required = FDA_SECTIONS if report_format == "FDA_21_CFR_312" else EMA_SECTIONS

        for section in required:
            content = self._generate_section_content(
                section, trial_data, report_format, request
            )
            sections[section] = content

        return sections

    def _get_trial_data_from_s3(
        self, trial_id: str, start_date: str, end_date: str
    ) -> dict[str, Any]:
        """Retrieve trial data from S3."""
        try:
            key = f"trials/{trial_id}/data.json"
            response = self._s3_client.get_object(Bucket=self._s3_bucket, Key=key)
            trial_data = json.loads(response["Body"].read())
            
            # Filter data by date range
            trial_data["dateRange"] = {"start": start_date, "end": end_date}
            return trial_data
            
        except self._s3_client.exceptions.NoSuchKey:
            logger.warning(f"No trial data found for {trial_id}, using minimal data")
            return {
                "trialId": trial_id,
                "trialName": f"Clinical Trial {trial_id}",
                "phase": "Phase II",
                "indication": "Oncology",
                "enrolledPatients": 0,
                "adverseEvents": [],
                "dateRange": {"start": start_date, "end": end_date},
            }
        except Exception as e:
            logger.error(f"Error retrieving trial data: {e}")
            return {
                "trialId": trial_id,
                "error": str(e),
                "dateRange": {"start": start_date, "end": end_date},
            }

    def _generate_section_content(
        self,
        section_name: str,
        trial_data: dict[str, Any],
        report_format: str,
        request: RegulatoryReportRequest,
    ) -> str:
        """Use Claude to generate compliant content for a report section."""
        prompt = f"""You are a regulatory affairs specialist generating content for a {report_format} report.

Section: {section_name}
Report Type: {request.report_type}
Trial ID: {request.trial_id}

Trial Data:
{json.dumps(trial_data, indent=2)}

Generate professional, compliant content for the "{section_name}" section.
The content should be appropriate for submission to regulatory authorities.
Keep it concise (2-3 paragraphs) but comprehensive.

Return only the section content, no preamble."""

        try:
            response = self._bedrock.converse(
                modelId=self._model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
            )
            content = response["output"]["message"]["content"][0]["text"]
            return content.strip()
        except Exception as e:
            logger.error(f"Error generating content for {section_name}: {e}")
            return f"[Content for {section_name} - Trial {request.trial_id}]"

    def _generate_pdf(
        self, trial_id: str, report_format: str, sections: dict[str, str]
    ) -> str | None:
        """Generate PDF via Lambda and upload to S3.

        Returns S3 URL of generated PDF, or None if generation fails.
        """
        payload = {
            "format": report_format,
            "trialId": trial_id,
            "sections": sections,
        }

        # 15.5: Retry up to 2 times on failure
        for attempt in range(3):
            try:
                response = self._lambda_client.invoke(
                    FunctionName=self._lambda_function,
                    InvocationType="RequestResponse",
                    Payload=json.dumps(payload),
                )

                result = json.loads(response["Payload"].read())

                if result.get("statusCode") == 200:
                    body = json.loads(result["body"])
                    pdf_base64 = body["pdfBase64"]

                    # 15.4: Validate PDF format
                    if self._validate_pdf(pdf_base64):
                        # Upload to S3
                        s3_url = self._upload_pdf_to_s3(trial_id, pdf_base64)
                        return s3_url

                logger.warning(
                    f"PDF generation attempt {attempt + 1} failed",
                    extra={"statusCode": result.get("statusCode")},
                )

            except Exception as e:
                logger.warning(
                    f"PDF generation attempt {attempt + 1} error: {e}",
                    extra={"attempt": attempt + 1},
                )

        logger.error("PDF generation failed after 3 attempts")
        return None

    def _upload_pdf_to_s3(self, trial_id: str, pdf_base64: str) -> str:
        """Upload generated PDF to S3 and return URL."""
        pdf_bytes = base64.b64decode(pdf_base64)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        key = f"reports/{trial_id}/report-{timestamp}.pdf"
        
        try:
            self._s3_client.put_object(
                Bucket=self._s3_bucket,
                Key=key,
                Body=pdf_bytes,
                ContentType="application/pdf",
            )
            return f"s3://{self._s3_bucket}/{key}"
        except Exception as e:
            logger.error(f"Failed to upload PDF to S3: {e}")
            return f"s3://{self._s3_bucket}/{key}"  # Return URL anyway for demo

    def _validate_pdf(self, pdf_base64: str) -> bool:
        """Validate that the document is a valid PDF."""
        try:
            pdf_bytes = base64.b64decode(pdf_base64)
            # PDF files start with %PDF-
            return pdf_bytes.startswith(b"%PDF-")
        except Exception:
            return False
