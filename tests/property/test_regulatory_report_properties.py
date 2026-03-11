"""Property-based tests for Regulatory Report Agent."""

from hypothesis import given, strategies as st

from medflow.agents.regulatory_report import RegulatoryReportAgent
from medflow.shared.models.regulatory import RegulatoryReportRequest


@given(
    report_type=st.sampled_from(
        ["IND_Safety", "IND_Annual", "NDA_Submission", "EMA_IMPD"]
    )
)
def test_property_format_selection(report_type):
    """Property 10: Regulatory Report Format Selection.
    
    For any regulatory report request, the agent should identify the correct
    report format based on the regulatory body.
    """
    agent = RegulatoryReportAgent()
    
    request = RegulatoryReportRequest(
        report_type=report_type,
        trial_id="TRIAL-001",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )
    
    response = agent.generate(request)
    
    # EMA reports should use EMA_ICH_GCP format
    if report_type.startswith("EMA"):
        assert response.format == "EMA_ICH_GCP"
    # All other reports should use FDA_21_CFR_312 format
    else:
        assert response.format == "FDA_21_CFR_312"


@given(
    report_type=st.sampled_from(
        ["IND_Safety", "IND_Annual", "NDA_Submission", "EMA_IMPD"]
    )
)
def test_property_section_completeness(report_type):
    """Property 11: Regulatory Report Section Completeness.
    
    For any generated regulatory report, all sections required by the
    applicable regulation should be present in the report.
    """
    agent = RegulatoryReportAgent()
    
    request = RegulatoryReportRequest(
        report_type=report_type,
        trial_id="TRIAL-001",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )
    
    response = agent.generate(request)
    
    # Define required sections per format
    if response.format == "FDA_21_CFR_312":
        required = [
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
    else:  # EMA_ICH_GCP
        required = [
            "Administrative Information",
            "Quality Information",
            "Non-Clinical Information",
            "Clinical Information",
            "Risk Assessment",
        ]
    
    # All required sections should be present
    for section in required:
        assert section in response.sections


@given(
    report_type=st.sampled_from(
        ["IND_Safety", "IND_Annual", "NDA_Submission", "EMA_IMPD"]
    )
)
def test_property_missing_data_reporting(report_type):
    """Property 12: Missing Data Reporting.
    
    For any regulatory report with incomplete required data, the agent
    should generate a list of missing elements.
    """
    agent = RegulatoryReportAgent()
    
    request = RegulatoryReportRequest(
        report_type=report_type,
        trial_id="TRIAL-001",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )
    
    response = agent.generate(request)
    
    # missing_elements should be a list
    assert isinstance(response.missing_elements, list)
    
    # If there are missing elements, PDF should not be generated
    if response.missing_elements:
        assert response.pdf_url is None
    
    # If no missing elements, PDF should be generated
    if not response.missing_elements:
        assert response.pdf_url is not None


@given(
    report_type=st.sampled_from(
        ["IND_Safety", "IND_Annual", "NDA_Submission", "EMA_IMPD"]
    )
)
def test_property_lambda_data_structure(report_type):
    """Property 28: Regulatory Report Lambda Data Structure.
    
    For any PDF generation request to Lambda, the agent should pass
    structured report data containing all required sections.
    """
    agent = RegulatoryReportAgent()
    
    request = RegulatoryReportRequest(
        report_type=report_type,
        trial_id="TRIAL-001",
        start_date="2025-01-01",
        end_date="2025-12-31",
    )
    
    response = agent.generate(request)
    
    # Response should contain sections list
    assert isinstance(response.sections, list)
    assert len(response.sections) > 0
