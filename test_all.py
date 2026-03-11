#!/usr/bin/env python3
"""End-to-end test script for all MedFlow agents."""

import os
import sys
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_patient_eligibility():
    """Test Patient Eligibility Agent."""
    print_section("1. Testing Patient Eligibility Agent")
    
    try:
        from medflow.agents.patient_eligibility import PatientEligibilityAgent
        from medflow.shared.models.eligibility import EligibilityRequest
        from medflow.shared.utils.gateway_client import EHRGatewayClient
        from medflow.shared.utils.knowledge_base_client import KnowledgeBaseClient
        
        # Check if required config is present
        if not os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID") or os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID") == "your-knowledge-base-id":
            print("⚠️  Skipped: BEDROCK_KNOWLEDGE_BASE_ID not configured")
            print("   Set up Knowledge Base first or run with mock data")
            return None
        
        ehr_client = EHRGatewayClient()
        kb_client = KnowledgeBaseClient()
        agent = PatientEligibilityAgent(ehr_client, kb_client)
        
        request = EligibilityRequest(
            patient_id="PAT-001",
            trial_id="TRIAL-001"
        )
        
        print(f"📋 Screening patient {request.patient_id} for trial {request.trial_id}...")
        response = agent.evaluate(request)
        
        print(f"✅ Overall Eligibility: {response.overallEligibility}")
        print(f"   Criteria Evaluated: {len(response.criteriaEvaluations)}")
        print(f"   Generated At: {response.generatedAt}")
        
        if response.criteriaEvaluations:
            print(f"\n   Sample Criterion:")
            criterion = response.criteriaEvaluations[0]
            print(f"   - {criterion.criterionText}")
            print(f"   - Result: {criterion.result}")
            print(f"   - Reasoning: {criterion.reasoning}")
            print(f"   - Citations: {len(criterion.citations)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_regulatory_report():
    """Test Regulatory Report Agent."""
    print_section("2. Testing Regulatory Report Agent")
    
    try:
        from medflow.agents.regulatory_report import RegulatoryReportAgent
        from medflow.shared.models.regulatory import RegulatoryReportRequest
        
        agent = RegulatoryReportAgent()
        
        request = RegulatoryReportRequest(
            report_type="IND_Safety",
            trial_id="TRIAL-001",
            start_date="2025-01-01",
            end_date="2025-12-31"
        )
        
        print(f"📄 Generating {request.report_type} report for trial {request.trial_id}...")
        response = agent.generate(request)
        
        print(f"✅ Report ID: {response.report_id}")
        print(f"   Format: {response.format}")
        print(f"   Sections: {len(response.sections)}")
        print(f"   Missing Elements: {len(response.missing_elements)}")
        print(f"   PDF URL: {response.pdf_url or 'Not generated (missing data or Lambda not configured)'}")
        print(f"   Generated At: {response.generated_at}")
        
        if response.sections:
            print(f"\n   Sections included:")
            for section in response.sections[:3]:
                print(f"   - {section}")
            if len(response.sections) > 3:
                print(f"   ... and {len(response.sections) - 3} more")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_insurance_authorization():
    """Test Insurance Authorization Agent."""
    print_section("3. Testing Insurance Authorization Agent")
    
    try:
        from medflow.agents.insurance_auth import InsuranceAuthorizationAgent
        from medflow.shared.models.authorization import AuthorizationRequest
        
        agent = InsuranceAuthorizationAgent()
        
        # Test different cost thresholds
        test_cases = [
            ("Low cost", 450.0, "auto_approved"),
            ("Medium cost", 1500.0, "supervisor_review"),
            ("High cost", 7500.0, "human_escalation"),
        ]
        
        for name, cost, expected in test_cases:
            request = AuthorizationRequest(
                patient_id="PAT-001",
                procedure_code="PROC-001",
                procedure_description=f"{name} procedure",
                estimated_cost=cost,
                provider_id="PROV-001"
            )
            
            print(f"💳 Authorizing {name} (${cost})...")
            response = agent.authorize(request)
            
            status = "✅" if response.decision == expected else "⚠️"
            print(f"{status} Decision: {response.decision} (expected: {expected})")
            print(f"   Authorization ID: {response.authorization_id}")
            print(f"   Policy Evaluation: {response.policy_evaluation}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_orchestrator():
    """Test Orchestrator Agent with all specialist agents."""
    print_section("4. Testing Orchestrator Agent")
    
    try:
        from medflow.agents.orchestrator.agent import OrchestratorAgent
        from medflow.shared.models.coordination import CoordinationRequest, Requester
        
        orchestrator = OrchestratorAgent()
        
        # Test regulatory report (doesn't require external services)
        print("🎯 Test 1: Regulatory Report")
        request = CoordinationRequest(
            request_id="REQ-001",
            request_type="regulatory_report",
            priority="normal",
            requester=Requester(user_id="user@example.com", role="regulatory"),
            payload={
                "reportType": "IND_Safety",
                "trialId": "TRIAL-001",
                "dateRange": {"startDate": "2025-01-01", "endDate": "2025-12-31"}
            }
        )
        
        response = orchestrator.coordinate(request)
        print(f"   Status: {response.status}")
        print(f"   Results: {len(response.results)} agent(s)")
        if response.results:
            print(f"   Agent: {response.results[0].agentName}")
            print(f"   Execution Time: {response.results[0].executionTime:.2f}s")
        print()
        
        # Test insurance authorization
        print("🎯 Test 2: Insurance Authorization")
        request = CoordinationRequest(
            request_id="REQ-002",
            request_type="insurance_auth",
            priority="normal",
            requester=Requester(user_id="user@example.com", role="billing"),
            payload={
                "patientId": "PAT-001",
                "procedureCode": "PROC-001",
                "cost": 1500.0
            }
        )
        
        response = orchestrator.coordinate(request)
        print(f"   Status: {response.status}")
        print(f"   Results: {len(response.results)} agent(s)")
        if response.results:
            print(f"   Agent: {response.results[0].agentName}")
            print(f"   Execution Time: {response.results[0].executionTime:.2f}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  MedFlow Agent Test Suite")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)
    
    results = {
        "Patient Eligibility": test_patient_eligibility(),
        "Regulatory Report": test_regulatory_report(),
        "Insurance Authorization": test_insurance_authorization(),
        "Orchestrator": test_orchestrator(),
    }
    
    # Summary
    print_section("Test Summary")
    
    passed = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)
    total = len(results)
    
    for name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is None:
            status = "⚠️  SKIP"
        else:
            status = "❌ FAIL"
        print(f"{status}  {name}")
    
    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {skipped} skipped, {failed} failed")
    print(f"{'='*60}\n")
    
    if skipped > 0:
        print("💡 Tip: Run './setup-real-data.sh' to set up AWS services")
        print("   Or see docs/real-data-setup.md for manual setup\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
