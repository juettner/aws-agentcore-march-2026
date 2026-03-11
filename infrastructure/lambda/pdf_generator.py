"""Lambda function for PDF generation of regulatory reports.

Generates FDA 21 CFR Part 312 and EMA ICH-GCP compliant reports.
"""

import json
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def lambda_handler(event, context):
    """Generate PDF from structured report data.

    Args:
        event: Dict with 'format', 'trialId', 'sections' (dict of section_name: content)

    Returns:
        Dict with 'pdfBase64' (base64-encoded PDF bytes)
    """
    try:
        report_format = event["format"]
        trial_id = event["trialId"]
        sections = event["sections"]

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()

        # Title
        title = (
            f"FDA 21 CFR Part 312 Report"
            if report_format == "FDA_21_CFR_312"
            else "EMA ICH-GCP Report"
        )
        story.append(Paragraph(title, styles["Title"]))
        story.append(Spacer(1, 12))

        # Trial ID
        story.append(Paragraph(f"Trial ID: {trial_id}", styles["Normal"]))
        story.append(
            Paragraph(
                f"Generated: {datetime.utcnow().isoformat()}",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 24))

        # Sections
        for section_name, content in sections.items():
            story.append(Paragraph(section_name, styles["Heading2"]))
            story.append(Paragraph(content or "N/A", styles["Normal"]))
            story.append(Spacer(1, 12))

        doc.build(story)

        pdf_bytes = buffer.getvalue()
        import base64

        return {
            "statusCode": 200,
            "body": json.dumps({"pdfBase64": base64.b64encode(pdf_bytes).decode()}),
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
