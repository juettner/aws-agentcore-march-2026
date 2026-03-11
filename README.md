# MedFlow Clinical Trial Coordination System

A multi-agent AI system for clinical trial and patient care coordination, built on **Amazon Bedrock AgentCore** and the **Strands** framework. MedFlow demonstrates how specialized AI agents can automate complex clinical workflows — patient screening, adverse event monitoring, and insurance authorization — while enforcing deterministic policy guardrails and building institutional memory over time.

---

## What It Does

MedFlow orchestrates seven specialized agents across three core workflows, each backed by a dedicated AgentCore capability:

| Workflow | AgentCore Capability | What the agent does |
|---|---|---|
| **Patient Eligibility Screening** | Gateway + Knowledge Base | Retrieves EHR data via MCP, queries Bedrock KB for trial protocols, evaluates each criterion with Claude |
| **Adverse Event Detection** | Memory | Scores severity, matches toxicity patterns, stores episodes for pattern learning over time |
| **Insurance Authorization** | Verified Permissions (Cedar) | Routes by cost, evaluates Cedar policies deterministically, submits to insurance API |

Supporting agents handle regulatory PDF generation (FDA/EMA compliant), patient voice check-ins (Amazon Nova Sonic), and multi-patient trial scheduling (A2A swarm coordination).

---

## Architecture

```
                    ┌─────────────────────────────────┐
                    │   AgentCore Runtime              │
                    │   (managed execution, 8h window) │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │       Orchestrator Agent         │
                    │       (Agent-as-Tool routing)    │
                    └──┬──────┬──────┬──────┬─────────┘
                       │      │      │      │
           ┌───────────┘  ┌───┘  ┌───┘  ┌──┘
           ▼              ▼      ▼      ▼
    Patient         Adverse   Insurance  Regulatory
    Eligibility     Event     Auth       Report
    Agent           Monitor   Agent      Agent
       │               │         │
       ▼               ▼         ▼
    Gateway +       Memory    Verified
    Knowledge Base  (episodic) Permissions
```

### The Seven Agents

| Agent | Pattern | Key services |
|---|---|---|
| **Orchestrator** | Agent-as-Tool | Routes to all specialists |
| **Patient Eligibility** | KB + Gateway | Bedrock KB, AgentCore Gateway → EHR Lambda |
| **Adverse Event Monitor** | Episodic Memory | AgentCore Memory (semantic + summary strategies) |
| **Regulatory Report** | Lambda integration | Bedrock Runtime, Lambda (PDF generation) |
| **Insurance Authorization** | Policy enforcement | Amazon Verified Permissions, AgentCore Gateway |
| **Patient Communication** | BidiAgent | Amazon Nova Sonic (bidirectional speech) |
| **Trial Coordinator** | Swarm / A2A | A2A Protocol, multi-agent scheduling |

---

## Project Structure

```
.
├── agents/                          # AgentCore Runtime entrypoints (deployed)
│   ├── patient_eligibility/
│   │   └── runtime_agent.py         # BedrockAgentCoreApp — eligibility screening
│   ├── adverse_event/
│   │   └── runtime_agent.py         # BedrockAgentCoreApp — adverse event monitor
│   └── insurance_auth/
│       └── runtime_agent.py         # BedrockAgentCoreApp — insurance authorization
│
├── medflow/                         # Core application code
│   ├── agents/                      # Agent implementations (7 agents)
│   │   ├── orchestrator/
│   │   ├── patient_eligibility/
│   │   ├── adverse_event/
│   │   ├── regulatory_report/
│   │   ├── insurance_auth/
│   │   ├── patient_comm/
│   │   └── trial_coordinator/
│   └── shared/
│       ├── models/                  # Pydantic / dataclass models
│       ├── protocols/               # A2A communication protocols
│       └── utils/                   # AWS client wrappers
│           ├── gateway_client.py    # AgentCore Gateway (MCP / SigV4)
│           ├── memory_client.py     # AgentCore Memory
│           ├── knowledge_base_client.py
│           ├── nova_sonic_client.py
│           ├── audit_logger.py      # 7-year retention, FDA-compliant
│           ├── checkpoint.py        # Checkpoint / resume
│           └── retry.py             # Exponential backoff
│
├── demo/
│   └── run_demo.py                  # Interactive demo runner (3 scenarios)
│
├── infrastructure/
│   ├── deploy_all.sh                # Master deployment script
│   ├── deploy_lambdas.sh
│   ├── deploy.sh                    # IAM + CloudWatch setup
│   ├── iam/                         # IAM role and policy JSON
│   ├── lambda/                      # Lambda function source + zips
│   │   ├── ehr_mock_lambda.py       # Mock EHR API
│   │   └── pdf_generator.py         # FDA/EMA PDF reports
│   ├── kb-docs/                     # Trial protocol documents (uploaded to S3 → KB)
│   ├── services/                    # AgentCore service configs (YAML)
│   ├── cloudwatch/                  # Log group definitions
│   └── scripts/
│       ├── setup_verified_permissions.py
│       └── populate_trial_data.py
│
├── tests/
│   ├── unit/                        # 54+ unit tests
│   ├── property/                    # Hypothesis property-based tests
│   └── integration/                 # Integration tests (mock-based)
│
├── docs/                            # Presentation materials
│   ├── AgentCore-MedFlow-Presentation-SDG.pptx
│   ├── presentation-guide.md
│   ├── presentation-outline.md
│   └── presentation-ia-presenter.md
│
├── DEMO_SCRIPT.md                   # Live demo presenter script
├── .env.example                     # Environment variable template
└── requirements.txt
```

---

## Prerequisites

- Python 3.11+
- AWS CLI v2, configured with credentials for your target account
- Docker, Finch, or Podman (for local Runtime testing only)
- An AWS account with access to:
  - Amazon Bedrock (Claude 3.5 Haiku, Titan Embed Text v2)
  - Amazon OpenSearch Serverless
  - Amazon Verified Permissions
  - Amazon Bedrock AgentCore (Runtime, Gateway, Memory)

---

## Deployment

All infrastructure is provisioned by a single script. Run once from the project root:

```bash
# 1. Set up Python environment
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure AWS credentials
aws configure

# 3. Deploy all infrastructure
#    Creates: Lambda functions, OpenSearch index, Bedrock Knowledge Base,
#    Gateway target, S3 bucket, IAM role, CloudWatch log groups
cd infrastructure && ./deploy_all.sh

# 4. Copy and fill in the generated environment file
cp .env.example .env
# deploy_all.sh writes most values automatically — verify they look right
```

### Deploy the AgentCore Runtime Agents

Each of the three demo agents runs as a managed Runtime container. Deploy them individually:

```bash
# Patient Eligibility Agent
agentcore configure \
  --entrypoint agents/patient_eligibility/runtime_agent.py \
  --name medflow_eligibility \
  --execution-role arn:aws:iam::<account>:role/MedFlowAgentCoreRuntimeRole \
  --requirements-file requirements.txt --region us-west-2 --max-lifetime 28800 --non-interactive
agentcore launch
# Paste the returned agentRuntimeArn into .env as AGENTCORE_ELIGIBILITY_RUNTIME_ARN

# Adverse Event Agent
agentcore configure \
  --entrypoint agents/adverse_event/runtime_agent.py \
  --name medflow_adverse_event \
  --execution-role arn:aws:iam::<account>:role/MedFlowAgentCoreRuntimeRole \
  --requirements-file requirements.txt --region us-west-2 --max-lifetime 28800 --non-interactive
agentcore launch
# → AGENTCORE_ADVERSE_EVENT_RUNTIME_ARN

# Insurance Auth Agent
agentcore configure \
  --entrypoint agents/insurance_auth/runtime_agent.py \
  --name medflow_insurance_auth \
  --execution-role arn:aws:iam::<account>:role/MedFlowAgentCoreRuntimeRole \
  --requirements-file requirements.txt --region us-west-2 --max-lifetime 28800 --non-interactive
agentcore launch
# → AGENTCORE_INSURANCE_AUTH_RUNTIME_ARN
```

---

## Running the Demo

```bash
python demo/run_demo.py
```

The demo runs three live scenarios against the deployed Runtime agents:

1. **Patient Eligibility Screening** — Sarah Johnson (PAT-001) screened for a GLP-1 diabetes trial. Gateway retrieves EHR data, Knowledge Base retrieves protocol criteria, Claude evaluates each criterion.

2. **Adverse Event Detection** — Michael Chen (PAT-002), Grade 3 Neutropenia on Day 14 of an oncology trial. Severity scored, patterns matched, episode stored in AgentCore Memory for future pattern learning.

3. **Insurance Authorization** — Three authorization amounts ($250 / $2,500 / $15,000) evaluated against Cedar policies in Amazon Verified Permissions. Auto-approve, supervisor review, and medical director escalation demonstrated deterministically.

If a Runtime ARN is not configured in `.env`, that scenario falls back to direct boto3 calls — so the demo stays runnable while you deploy incrementally.

See **`DEMO_SCRIPT.md`** for the full presenter script with narration cues and talking points.

---

## Testing

```bash
# All tests
pytest

# By suite
pytest tests/unit/       # 54+ unit tests
pytest tests/property/   # Hypothesis property-based tests
pytest tests/integration/

# Specific agent
pytest tests/unit/test_adverse_event_agent.py -v
```

---

## Key Design Decisions

**AgentCore Runtime over Lambda for agent execution.** Runtime provides 8-hour execution windows (clinical workflows run long), managed checkpointing, and session continuity — none of which Lambda offers out of the box.

**Cedar policies for authorization routing, not LLM prompts.** Insurance authorization thresholds are business rules that must be deterministic, auditable, and updatable without code changes. Verified Permissions handles this; the agent handles clinical reasoning.

**AgentCore Memory with two strategies.** The adverse event monitor writes each episode with both a semantic extraction strategy (for clinical similarity search) and a session summary strategy (for contextual roll-ups). Over time this builds population-level pattern detection.

**AgentCore Gateway for EHR integration.** The Gateway transforms the mock EHR REST API into MCP tools, meaning agent code never contains raw HTTP logic or auth handling — it just calls named tools.

---

## Compliance Notes

- Audit logs are written to CloudWatch with 7-year retention (FDA 21 CFR Part 11)
- All agent operations produce structured audit records via `shared/utils/audit_logger.py`
- Cedar policy decisions are logged with the matching policy ID for traceability
- This is a demonstration system — production deployment requires a full compliance review

---

## License

Demonstration project. Not for production clinical use without independent validation, security review, and regulatory clearance. And even then, just don't. This is just a demo.
