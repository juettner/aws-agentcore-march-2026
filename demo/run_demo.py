#!/usr/bin/env python3
"""MedFlow Demo Runner - Interactive guided demo of AgentCore capabilities.

This script walks through three demo scenarios:
1. Patient Eligibility Screening (Knowledge Base + Gateway)
2. Adverse Event Detection (Memory + Pattern Matching)
3. Insurance Authorization (Verified Permissions / Cedar Policies)

Run: python demo/run_demo.py
"""

import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# ============================================================================
# Configuration
# ============================================================================
REGION = os.getenv("AWS_REGION", "us-west-2")
ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID", "")
MEMORY_ID = os.getenv("AGENTCORE_MEMORY_ID", "")
GATEWAY_ID = os.getenv("AGENTCORE_GATEWAY_ID", "")
GATEWAY_URL = os.getenv("AGENTCORE_GATEWAY_URL", "")
POLICY_STORE_ID = os.getenv("VERIFIED_PERMISSIONS_POLICY_STORE_ID", "")
KB_ID = os.getenv("BEDROCK_KNOWLEDGE_BASE_ID", "PENDING_DEPLOYMENT")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20251022-v2:0")
ELIGIBILITY_RUNTIME_ARN   = os.getenv("AGENTCORE_ELIGIBILITY_RUNTIME_ARN", "")
ADVERSE_EVENT_RUNTIME_ARN = os.getenv("AGENTCORE_ADVERSE_EVENT_RUNTIME_ARN", "")
INSURANCE_AUTH_RUNTIME_ARN = os.getenv("AGENTCORE_INSURANCE_AUTH_RUNTIME_ARN", "")
PDF_LAMBDA = os.getenv("LAMBDA_PDF_GENERATOR_ARN",
    f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:medflow-pdf-generator")
EHR_LAMBDA = os.getenv("LAMBDA_EHR_MOCK_ARN",
    f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:medflow-ehr-mock-api")

# AWS clients
session = boto3.Session(region_name=REGION)
lambda_client = session.client("lambda")
bedrock_runtime = session.client("bedrock-runtime")
bedrock_agent_runtime = session.client("bedrock-agent-runtime")
agentcore_runtime = session.client("bedrock-agentcore")
verified_permissions = session.client("verifiedpermissions")
logs_client = session.client("logs")

# CloudWatch log groups for each Runtime agent
_AGENT_LOG_GROUPS = {
    "eligibility":    "arn:aws:bedrock-agentcore:us-west-2:853297241922:runtime/medflow_eligibility-FIoHSxAPuc",
    "adverse_event":  "arn:aws:bedrock-agentcore:us-west-2:853297241922:runtime/medflow_adverse_event-wSgFb8CyBo",
    "insurance_auth": "arn:aws:bedrock-agentcore:us-west-2:853297241922:runtime/medflow_insurance_auth-A3lEzCDHlz",
}
_LOG_GROUP_NAMES = {
    "eligibility":    "/aws/bedrock-agentcore/runtimes/medflow_eligibility-FIoHSxAPuc-DEFAULT",
    "adverse_event":  "/aws/bedrock-agentcore/runtimes/medflow_adverse_event-wSgFb8CyBo-DEFAULT",
    "insurance_auth": "/aws/bedrock-agentcore/runtimes/medflow_insurance_auth-A3lEzCDHlz-DEFAULT",
}


# ============================================================================
# Helpers
# ============================================================================
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def header(text: str):
    print(f"\n{BOLD}{BLUE}{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}{RESET}\n")


def step(num: int, text: str):
    print(f"  {CYAN}[Step {num}]{RESET} {text}")


def result(text: str):
    print(f"  {GREEN}✓{RESET} {text}")


def warn(text: str):
    print(f"  {YELLOW}⚠{RESET} {text}")


def error(text: str):
    print(f"  {RED}✗{RESET} {text}")


def pause(message: str = "Press Enter to continue..."):
    input(f"\n  {YELLOW}▶{RESET} {message}")


# Messages to skip — setup noise not interesting for the audience
_LOG_SKIP = ("CloudWatch logging enabled", "Found credentials", "urllib3", "botocore")

# Friendly labels for known log patterns
def _format_log_line(msg: str) -> str | None:
    """Return a display string for a log message, or None to suppress it."""
    if any(msg.startswith(s) for s in _LOG_SKIP):
        return None
    if "HTTP Request: POST https://medflow-ehr-gateway" in msg:
        return f"{CYAN}[Gateway]{RESET} EHR tool call → Lambda"
    if "HTTP Request:" in msg:
        return None  # suppress other HTTP noise
    return msg


def invoke_with_trace(agent_key: str, invoke_fn, *args, **kwargs) -> dict | None:
    """Run an agent invocation while streaming its CloudWatch logs to stdout.

    Fires the invocation in a background thread, polls the application-logs
    stream every second, and prints each new log line as it arrives.
    Returns the invocation result when complete.
    """
    log_group = _LOG_GROUP_NAMES.get(agent_key, "")
    result_box: dict = {"value": None, "done": False}
    start_ms = int(time.time() * 1000)

    def _run():
        try:
            result_box["value"] = invoke_fn(*args, **kwargs)
        except Exception as exc:
            result_box["value"] = {"error": str(exc)}
        finally:
            result_box["done"] = True

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    seen: set[str] = set()
    drain_rounds = 0  # keep polling briefly after done to catch trailing flushes

    print(f"  {CYAN}[Agent running — live trace]{RESET}")
    while not result_box["done"] or drain_rounds < 4:
        if result_box["done"]:
            drain_rounds += 1
        time.sleep(0.8)
        if not log_group:
            continue
        try:
            resp = logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName="application-logs",
                startTime=start_ms,
                startFromHead=True,
            )
            for event in resp.get("events", []):
                key = f"{event['timestamp']}:{event['message'][:40]}"
                if key in seen:
                    continue
                seen.add(key)
                line = _format_log_line(event["message"].strip())
                if line:
                    print(f"    {CYAN}→{RESET} {line}")
        except Exception:
            pass  # log group may not exist yet; silently continue

    thread.join(timeout=2)
    return result_box["value"]


def invoke_eligibility_runtime(patient_id: str, trial_id: str) -> dict | None:
    """Invoke the patient eligibility agent via AgentCore Runtime.

    Returns parsed response dict, or None if the Runtime ARN isn't configured.
    """
    if not ELIGIBILITY_RUNTIME_ARN:
        return None

    agentcore_client = session.client("bedrock-agentcore")
    session_id = str(uuid.uuid4())
    payload = json.dumps({"patient_id": patient_id, "trial_id": trial_id}).encode()

    response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=ELIGIBILITY_RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=payload,
    )

    raw = response.get("response", response.get("payload", b"{}"))
    if hasattr(raw, "read"):
        raw = raw.read()
    return json.loads(raw)


def _invoke_runtime(arn: str, payload: dict) -> dict | None:
    """Generic AgentCore Runtime invocation. Returns None if ARN not set."""
    if not arn:
        return None
    agentcore_client = session.client("bedrock-agentcore")
    response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps(payload).encode(),
    )
    raw = response.get("response", response.get("payload", b"{}"))
    if hasattr(raw, "read"):
        raw = raw.read()
    return json.loads(raw)


def invoke_adverse_event_runtime(patient_id: str, symptoms: list, medications: list,
                                  timeline: str, store: bool = True) -> dict | None:
    return _invoke_runtime(ADVERSE_EVENT_RUNTIME_ARN, {
        "patient_id": patient_id,
        "symptoms": symptoms,
        "medications": medications,
        "timeline": timeline,
        "store_outcome": store,
    })


def invoke_insurance_auth_runtime(patient_id: str, procedure_code: str,
                                   description: str, amount: float) -> dict | None:
    return _invoke_runtime(INSURANCE_AUTH_RUNTIME_ARN, {
        "patient_id": patient_id,
        "procedure_code": procedure_code,
        "procedure_description": description,
        "estimated_cost": amount,
        "provider_id": "PROV-001",
    })


def invoke_ehr_lambda(tool_name: str, tool_input: dict) -> dict:
    """Invoke the EHR mock Lambda directly."""
    response = lambda_client.invoke(
        FunctionName=EHR_LAMBDA.split(":")[-1] if ":" in EHR_LAMBDA else EHR_LAMBDA,
        InvocationType="RequestResponse",
        Payload=json.dumps({"toolName": tool_name, "toolInput": tool_input}),
    )
    payload = json.loads(response["Payload"].read())
    if "body" in payload:
        return json.loads(payload["body"])
    return payload


def pretty_json(data: dict, indent: int = 4) -> str:
    return json.dumps(data, indent=indent, default=str)


# ============================================================================
# Scenario 1: Patient Eligibility Screening
# ============================================================================
def demo_scenario_1():
    header("SCENARIO 1: Patient Eligibility Screening")
    print(f"  {BOLD}Context:{RESET} Simon Schwob (PAT-001) is being screened for")
    print(f"  TRIAL-001 (Type 2 Diabetes, GLP-1 Receptor Agonist study)")
    print()
    print(f"  {BOLD}AgentCore Services Demonstrated:{RESET}")
    print(f"    • Gateway → MCP tool call to EHR Lambda (patient records)")
    print(f"    • Knowledge Base → RAG retrieval of trial protocol criteria")
    print(f"    • Bedrock → Claude reasoning over eligibility criteria")
    print()

    # ── Path A: invoke the deployed Runtime agent ──────────────────────────
    if ELIGIBILITY_RUNTIME_ARN:
        pause("Invoke the patient eligibility agent via AgentCore Runtime...")
        step(1, f"invoke_agent_runtime → {ELIGIBILITY_RUNTIME_ARN[:60]}...")
        print(f"    Payload: {{patient_id: PAT-001, trial_id: TRIAL-001}}")
        print()

        try:
            runtime_result = invoke_with_trace(
                "eligibility", invoke_eligibility_runtime, "PAT-001", "TRIAL-001"
            )
            if runtime_result and "error" not in runtime_result:
                overall = runtime_result.get("overallEligibility", "unknown")
                color = GREEN if overall == "eligible" else RED if overall == "ineligible" else YELLOW
                result(f"Overall eligibility: {color}{overall.upper()}{RESET}")
                print()
                for evaluation in runtime_result.get("criteriaEvaluations", []):
                    criterion_result = evaluation.get("result", "unknown").lower()
                    c = GREEN if criterion_result == "pass" else RED if criterion_result == "fail" else YELLOW
                    print(f"    {c}{'✓' if criterion_result == 'pass' else '✗'}{RESET} "
                          f"{evaluation.get('criterionText', '')[:80]}")
                    print(f"       {evaluation.get('reasoning', '')}")
                print()
                result(f"{BOLD}Running in AgentCore Runtime — Gateway + KB + Bedrock all invoked inside the container{RESET}")
            else:
                warn(f"Runtime returned an error: {runtime_result}")
        except ClientError as e:
            warn(f"Runtime invocation failed: {e}")

    # ── Path B: direct boto3 walkthrough (fallback / if Runtime not deployed) ──
    else:
        warn("AGENTCORE_ELIGIBILITY_RUNTIME_ARN not set — running direct AWS service calls")
        warn("Deploy the Runtime agent first: agentcore launch (from project root)")
        print()

        # Step 1: Fetch patient record via Gateway (Lambda)
        pause("Step 1: Fetch patient record via AgentCore Gateway...")
        step(1, "Calling Gateway → EHR Lambda: get_patient_record(PAT-001)")
        patient = invoke_ehr_lambda("get_patient_record", {"patientId": "PAT-001"})
        print()
        result(f"Patient: {patient['name']}, Age: {patient['age']}, Diagnosis: {patient['diagnosis']}")
        result(f"Current medications: {', '.join(m['name'] for m in patient['currentMedications'])}")
        result(f"Allergies: {', '.join(patient['allergies'])}")

        # Step 2: Fetch lab results
        pause("Step 2: Fetch lab results via Gateway...")
        step(2, "Calling Gateway → EHR Lambda: get_lab_results(PAT-001)")
        labs = invoke_ehr_lambda("get_lab_results", {"patientId": "PAT-001"})
        print()
        for lab in labs.get("results", []):
            status_color = RED if lab["status"] == "HIGH" else GREEN
            result(f"  {lab['testName']}: {lab['value']} {lab['unit']} "
                   f"(ref: {lab['referenceRange']}) [{status_color}{lab['status']}{RESET}]")

        # Step 3: Query Knowledge Base for trial protocol
        pause("Step 3: Retrieve trial protocol from Bedrock Knowledge Base...")
        step(3, f"Querying Knowledge Base ({KB_ID}) for TRIAL-001 criteria")

        if KB_ID and KB_ID != "PENDING_DEPLOYMENT":
            try:
                kb_response = bedrock_agent_runtime.retrieve(
                    knowledgeBaseId=KB_ID,
                    retrievalQuery={"text": "inclusion and exclusion criteria for TRIAL-001 Type 2 Diabetes GLP-1"},
                    retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
                )
                print()
                for i, r in enumerate(kb_response.get("retrievalResults", [])):
                    content = r.get("content", {}).get("text", "")[:200]
                    score = r.get("score", 0)
                    result(f"  Result {i+1} (score: {score:.3f}): {content}...")
            except ClientError as e:
                warn(f"Knowledge Base query failed: {e}")
        else:
            warn("Knowledge Base not yet deployed — showing protocol from trial data")
            result("  Inclusion: HbA1c 7.0-10.5%, BMI 25-45, stable metformin ≥1000mg/day")
            result("  Exclusion: Type 1 DM, pancreatitis history, severe hepatic impairment")

        # Step 4: Claude reasoning
        pause("Step 4: Claude evaluates eligibility criteria...")
        step(4, f"Invoking Bedrock model ({MODEL_ID}) for eligibility reasoning")

        prompt = f"""You are a clinical trial eligibility screening AI agent.
Based on the following patient data and trial criteria, evaluate whether this patient
is eligible for TRIAL-001.

PATIENT DATA:
{json.dumps(patient, indent=2)}

LAB RESULTS:
{json.dumps(labs, indent=2)}

TRIAL-001 CRITERIA (from Knowledge Base):
- Inclusion: Age 18-75, confirmed T2DM ≥6 months, HbA1c 7.0-10.5%, BMI 25-45,
  stable metformin ≥1000mg/day for 8 weeks, eGFR ≥30
- Exclusion: Type 1 DM, DKA within 6 months, pancreatitis history, severe hepatic
  impairment, current insulin use

Evaluate each criterion and provide your overall eligibility determination.
Be concise but thorough."""

        try:
            model_response = bedrock_runtime.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                }),
            )
            response_body = json.loads(model_response["body"].read())
            reasoning = response_body["content"][0]["text"]
            print()
            print(f"  {BOLD}Claude's Eligibility Assessment:{RESET}")
            for line in reasoning.split("\n"):
                if line.strip():
                    print(f"    {line}")
        except ClientError as e:
            warn(f"Model invocation failed: {e}")
            result("  [Demo fallback] Patient PAT-001 is ELIGIBLE for TRIAL-001")
            result("  HbA1c 7.8% within range, age 45 within range, on metformin 1000mg")

    print()
    result(f"{BOLD}Scenario 1 Complete — Patient screening with real AWS services{RESET}")


# ============================================================================
# Scenario 2: Adverse Event Detection
# ============================================================================
def demo_scenario_2():
    header("SCENARIO 2: Adverse Event Detection & Pattern Matching")
    print(f"  {BOLD}Context:{RESET} Matt Leising (PAT-002) reports Grade 3 Neutropenia")
    print(f"  during TRIAL-002 (NSCLC, carboplatin + MF-5120)")
    print()
    print(f"  {BOLD}AgentCore Services Demonstrated:{RESET}")
    print(f"    • Gateway → Fetch patient data and adverse events")
    print(f"    • Memory → Store episode + retrieve similar historical cases")
    print(f"    • Bedrock → Severity assessment and recommended actions")
    print()

    # ── Path A: invoke via Runtime ───────────────────────────────────────────
    if ADVERSE_EVENT_RUNTIME_ARN:
        pause("Invoke the adverse event monitor via AgentCore Runtime...")
        step(1, f"invoke_agent_runtime → {ADVERSE_EVENT_RUNTIME_ARN[:60]}...")
        print(f"    Patient PAT-002 | Grade 3 Neutropenia | carboplatin + MF-5120")
        print()
        try:
            rt = invoke_with_trace(
                "adverse_event", invoke_adverse_event_runtime,
                patient_id="PAT-002",
                symptoms=["neutropenia", "fatigue"],
                medications=["carboplatin", "MF-5120"],
                timeline="Grade 3 Neutropenia detected on Day 14, ANC 850/μL",
                store=True,
            )
            if rt and "error" not in rt:
                grade = rt.get("severity_grade", "?")
                alert = rt.get("alert_generated", False)
                grade_color = RED if grade >= 3 else YELLOW
                result(f"Severity grade: {grade_color}{grade}/5{RESET}  |  "
                       f"Alert generated: {RED + 'YES' + RESET if alert else GREEN + 'no' + RESET}")
                result(f"Matched patterns: {rt.get('matched_patterns', []) or 'none'}")
                result(f"Historical cases found: {len(rt.get('historical_cases', []))}")
                result(f"Recommendation: {rt.get('recommendation', '')}")
                if alert:
                    print()
                    print(f"  {RED}{BOLD}⚠  Grade ≥3 detected — episode written to AgentCore Memory{RESET}")
            else:
                warn(f"Runtime returned an error: {rt}")
        except ClientError as e:
            warn(f"Runtime invocation failed: {e}")
        print()
        result(f"{BOLD}Scenario 2 Complete — Adverse event with Memory + pattern detection{RESET}")
        return

    # ── Path B: direct boto3 walkthrough (fallback) ──────────────────────────
    warn("AGENTCORE_ADVERSE_EVENT_RUNTIME_ARN not set — running direct AWS service calls")
    print()

    # Step 1: Fetch adverse events
    pause("Step 1: Fetch adverse events from EHR via Gateway...")
    step(1, "Calling Gateway → EHR Lambda: get_adverse_events(PAT-002)")
    ae_data = invoke_ehr_lambda("get_adverse_events", {"patientId": "PAT-002"})
    print()
    for ae in ae_data.get("adverseEvents", []):
        sev_color = RED if ae["severity"] == "SEVERE" else YELLOW if ae["severity"] == "MODERATE" else GREEN
        result(f"  {ae['eventId']}: {ae['description']} "
               f"[{sev_color}{ae['severity']}{RESET}] "
               f"Causality: {ae['causalityAssessment']} | Status: {ae['status']}")

    # Step 2: Store episode in AgentCore Memory
    pause("Step 2: Store adverse event in AgentCore Memory...")
    step(2, f"Writing to Memory ({MEMORY_ID}) — semantic + summary strategies")

    episode_text = (
        "Patient PAT-002 (Matt Leising, 62M, NSCLC Stage IIIA) on carboplatin + MF-5120. "
        "Grade 3 Neutropenia detected: ANC 1.1 x10^9/L (reference 1.8-7.7), WBC 3.2 x10^9/L. "
        "Prior history: fatigue Grade 2 since Feb 25. Causality assessment: DEFINITE for "
        "carboplatin-induced myelosuppression."
    )

    try:
        agentcore_runtime.ingest_memory_events(
            memoryId=MEMORY_ID,
            events=[{
                "actorId": "PAT-002",
                "sessionId": f"ae-session-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "eventId": f"evt-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "event": {"role": "ASSISTANT", "content": episode_text},
                "eventTimestamp": datetime.utcnow().isoformat(),
            }],
        )
        result("Episode stored in AgentCore Memory")
        result("  Semantic strategy: adverseEventSemanticMemory (for pattern matching)")
        result("  Summary strategy: sessionSummary (for session roll-ups)")
    except ClientError as e:
        warn(f"Memory write failed: {e}")

    # Step 3: Query memory for similar cases
    pause("Step 3: Retrieve similar historical cases from Memory...")
    step(3, "Querying semantic memory for carboplatin + neutropenia pattern")

    try:
        memory_results = agentcore_runtime.retrieve_memory(
            memoryId=MEMORY_ID,
            strategyId="adverseEventSemanticMemory-RF0Y1b3aw2",
            query="neutropenia carboplatin chemotherapy severe",
            namespace="/strategies/adverseEventSemanticMemory-RF0Y1b3aw2/actors/*/",
            maxResults=5,
        )
        events = memory_results.get("events", [])
        print()
        if events:
            result(f"Found {len(events)} similar historical cases")
            for evt in events[:3]:
                score = evt.get("score", 0)
                content = evt.get("event", {}).get("content", "")[:150]
                result(f"  Score {score:.3f}: {content}...")
        else:
            result("No prior cases yet — this is the first episode stored")
            result("  (In a real deployment, memory would accumulate patterns over time)")
    except ClientError as e:
        warn(f"Memory retrieval failed: {e}")

    # Step 4: Claude severity assessment
    pause("Step 4: Claude assesses severity and recommends actions...")
    step(4, f"Invoking {MODEL_ID} for clinical assessment")

    try:
        labs = invoke_ehr_lambda("get_lab_results", {"patientId": "PAT-002"})
        prompt = f"""You are an adverse event monitoring AI agent for clinical trials.
Assess this adverse event and provide recommended actions.

PATIENT: Matt Leising (PAT-002), 62M, NSCLC Stage IIIA
TREATMENT: Carboplatin AUC 5 + MF-5120 (anti-PD-L1/VEGF bispecific) q3w

CURRENT ADVERSE EVENT: Grade 3 Neutropenia
LAB RESULTS:
{json.dumps(labs, indent=2)}

REPORTED EVENTS: Grade 3 Neutropenia (ANC 1.1, onset March 5), Grade 2 Fatigue (ongoing since Feb 25)

Per the TRIAL-002 protocol dose modification rules:
- Grade 3 Neutropenia (ANC 500-999): Hold carboplatin, resume at AUC 4 when ANC ≥ 1500
- Grade 4 Neutropenia (ANC <500): Hold all treatment, add G-CSF, resume at reduced doses

Provide: severity assessment, recommended immediate actions, SUSAR reporting requirements,
and dose modification recommendation. Be concise."""

        model_response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        response_body = json.loads(model_response["body"].read())
        assessment = response_body["content"][0]["text"]
        print()
        print(f"  {BOLD}Claude's Clinical Assessment:{RESET}")
        for line in assessment.split("\n"):
            if line.strip():
                print(f"    {line}")
    except ClientError as e:
        warn(f"Model invocation failed: {e}")

    print()
    result(f"{BOLD}Scenario 2 Complete — Adverse event with Memory + pattern detection{RESET}")


# ============================================================================
# Scenario 3: Insurance Authorization
# ============================================================================
def demo_scenario_3():
    header("SCENARIO 3: Insurance Authorization with Cedar Policies")
    print(f"  {BOLD}Context:{RESET} Three authorization requests with different amounts")
    print(f"  demonstrating deterministic Cedar policy evaluation")
    print()
    print(f"  {BOLD}AgentCore Services Demonstrated:{RESET}")
    print(f"    • Verified Permissions → Cedar policy evaluation")
    print(f"    • Gateway → Insurance authorization submission")
    print(f"    • Bedrock → Authorization reasoning and documentation")
    print()

    test_cases = [
        {"label": "Routine lab work",     "patient": "PAT-001", "amount": 250,   "procedure": "CPT-80053"},
        {"label": "CT scan / imaging",    "patient": "PAT-002", "amount": 2500,  "procedure": "CPT-71260"},
        {"label": "Specialty biologic",   "patient": "PAT-003", "amount": 15000, "procedure": "CPT-96413"},
    ]

    # ── Path A: invoke via Runtime ───────────────────────────────────────────
    if INSURANCE_AUTH_RUNTIME_ARN:
        for i, case in enumerate(test_cases, 1):
            pause(f"Step {i}: Authorize — {case['label']} (${case['amount']:,}) via Runtime...")
            step(i, f"{case['label']} | {case['patient']} | ${case['amount']:,}")
            print()
            try:
                rt = invoke_with_trace(
                    "insurance_auth", invoke_insurance_auth_runtime,
                    patient_id=case["patient"],
                    procedure_code=case["procedure"],
                    description=case["label"],
                    amount=case["amount"],
                )
                if rt and "error" not in rt:
                    decision = rt.get("decision", "unknown")
                    dec_color = (GREEN if decision == "auto_approved"
                                 else YELLOW if decision == "supervisor_review"
                                 else RED)
                    result(f"  Decision: {dec_color}{decision.upper().replace('_', ' ')}{RESET}")
                    result(f"  Auth ID:  {rt.get('authorization_id', 'N/A')}")
                    policies = rt.get("policy_evaluation", {})
                    for policy, passed in policies.items():
                        c = GREEN if passed else RED
                        result(f"  {c}{'✓' if passed else '✗'}{RESET} {policy.replace('_', ' ')}")
                else:
                    warn(f"Runtime returned an error: {rt}")
            except ClientError as e:
                warn(f"Runtime invocation failed: {e}")
            print()
        result(f"{BOLD}Scenario 3 Complete — Cedar policies enforce deterministic guardrails{RESET}")
        return

    # ── Path B: direct boto3 walkthrough (fallback) ──────────────────────────
    warn("AGENTCORE_INSURANCE_AUTH_RUNTIME_ARN not set — running direct AWS service calls")
    print()

    for i, case in enumerate(test_cases, 1):
        pause(f"Step {i}: Process authorization — {case['label']} (${case['amount']:,})...")
        step(i, f"Authorization: {case['label']} for {case['patient']} — ${case['amount']:,}")

        print()
        print(f"    {CYAN}Cedar Policy Evaluation:{RESET}")

        if case["amount"] < 500:
            action = "authorize"
            expected = "AUTO_APPROVED"
        elif case["amount"] < 5000:
            action = "review"
            expected = "PENDING_SUPERVISOR_REVIEW"
        else:
            action = "escalate"
            expected = "ESCALATED_TO_MEDICAL_DIRECTOR"

        try:
            avp_response = verified_permissions.is_authorized(
                policyStoreId=POLICY_STORE_ID,
                principal={"entityType": "MedFlow::Agent", "entityId": "InsuranceAuthAgent"},
                action={"actionType": "Action", "actionId": action},
                resource={"entityType": "MedFlow::Claim", "entityId": case["procedure"]},
                context={"contextMap": {"amount": {"long": case["amount"]}}},
            )
            decision = avp_response.get("decision", "UNKNOWN")
            print(f"    Policy action: {action}")
            print(f"    Decision: {GREEN if decision == 'ALLOW' else YELLOW}{decision}{RESET}")
            for det in avp_response.get("determiningPolicies", []):
                print(f"    Matched policy: {det.get('policyId', 'unknown')}")
        except ClientError as e:
            warn(f"  Verified Permissions call failed: {e}")
            print(f"    [Fallback] Expected decision based on amount: {expected}")

        auth_result = invoke_ehr_lambda("submit_insurance_auth", {
            "patientId": case["patient"],
            "procedureCode": case["procedure"],
            "amount": case["amount"],
            "description": case["label"],
        })

        decision = auth_result.get("decision", expected)
        dec_color = GREEN if "APPROVED" in decision else YELLOW if "REVIEW" in decision else RED
        result(f"  Result: {dec_color}{decision}{RESET}")
        result(f"  Auth ID: {auth_result.get('authorizationId', 'N/A')}")
        print()

    result(f"{BOLD}Scenario 3 Complete — Cedar policies enforce deterministic guardrails{RESET}")


# ============================================================================
# Main
# ============================================================================
def main():
    print(f"\n{BOLD}{BLUE}")
    print("  ╔═══════════════════════════════════════════════════════════════╗")
    print("  ║                                                               ║")
    print("  ║   MedFlow Clinical Trial Coordination System                  ║")
    print("  ║   Powered by Amazon Bedrock AgentCore                         ║")
    print("  ║                                                               ║")
    print("  ║   7 AI Agents • 9 AgentCore Services • Real AWS Infrastructure║")
    print("  ║                                                               ║")
    print("  ╚═══════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")

    print(f"  {BOLD}Configuration:{RESET}")
    print(f"    Region:    {REGION}")
    print(f"    Account:   {ACCOUNT_ID}")
    print(f"    Gateway:   {GATEWAY_ID}")
    print(f"    Memory:    {MEMORY_ID}")
    print(f"    KB:        {KB_ID}")
    print(f"    Model:     {MODEL_ID}")
    print(f"    Policy:    {POLICY_STORE_ID}")
    print()

    scenarios = {
        "1": ("Patient Eligibility Screening",         demo_scenario_1),
        "2": ("Adverse Event Detection",               demo_scenario_2),
        "3": ("Insurance Authorization (Cedar)",       demo_scenario_3),
        "a": ("Run all three in sequence",             None),
    }

    print(f"  {BOLD}Select a scenario:{RESET}")
    for key, (label, _) in scenarios.items():
        print(f"    [{key}] {label}")
    print()

    choice = input(f"  {YELLOW}▶{RESET} Enter choice (1/2/3/a): ").strip().lower()
    while choice not in scenarios:
        choice = input(f"  {YELLOW}▶{RESET} Invalid — enter 1, 2, 3, or a: ").strip().lower()

    print()

    if choice == "a":
        demo_scenario_1()
        pause("\nReady for Scenario 2?")
        demo_scenario_2()
        pause("\nReady for Scenario 3?")
        demo_scenario_3()
    else:
        scenarios[choice][1]()

    header("DEMO COMPLETE")
    print(f"  {BOLD}Summary of AWS services used:{RESET}")
    print(f"    • AgentCore Gateway (MCP) → Lambda-backed EHR API")
    print(f"    • AgentCore Memory → Semantic + Summary strategies")
    print(f"    • Bedrock Knowledge Base → RAG over trial protocols")
    print(f"    • Verified Permissions → Cedar policy evaluation")
    print(f"    • Bedrock Models → Claude 3.5 Haiku for reasoning")
    print(f"    • Lambda → PDF generation + mock EHR API")
    print(f"    • S3 → Trial data + reports + KB documents")
    print(f"    • CloudWatch → Agent execution logging")
    print()


if __name__ == "__main__":
    main()
