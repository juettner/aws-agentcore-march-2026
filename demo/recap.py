#!/usr/bin/env python3
"""MedFlow Demo Recap — Grand finale visual summary.

Fires all three agents in parallel, displays results in rich panels,
and prints a clinical summary table. Run after run_demo.py.

Usage:
    python demo/recap.py
"""

import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import boto3
from dotenv import load_dotenv
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

REGION = os.getenv("AWS_REGION", "us-west-2")
ELIGIBILITY_ARN   = os.getenv("AGENTCORE_ELIGIBILITY_RUNTIME_ARN", "")
ADVERSE_EVENT_ARN = os.getenv("AGENTCORE_ADVERSE_EVENT_RUNTIME_ARN", "")
INSURANCE_AUTH_ARN = os.getenv("AGENTCORE_INSURANCE_AUTH_RUNTIME_ARN", "")

console = Console()

# ── colour palette ─────────────────────────────────────────────────────────
BLUE    = "bold deep_sky_blue1"
GREEN   = "bold bright_green"
YELLOW  = "bold yellow"
RED     = "bold bright_red"
CYAN    = "bold cyan"
MAGENTA = "bold magenta"
DIM     = "dim white"


def _invoke(arn: str, payload: dict) -> tuple[dict, float]:
    """Invoke an agent runtime and return (result, elapsed_seconds)."""
    session = boto3.Session(region_name=REGION)
    client  = session.client("bedrock-agentcore")
    t0 = time.time()
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps(payload).encode(),
    )
    raw = resp.get("response", resp.get("payload", b"{}"))
    if hasattr(raw, "read"):
        raw = raw.read()
    elapsed = time.time() - t0
    return json.loads(raw), elapsed


def panel_eligibility(result: dict, elapsed: float) -> Panel:
    overall = result.get("overallEligibility", "unknown").upper()
    color   = GREEN if overall == "ELIGIBLE" else YELLOW if overall == "CONDITIONAL" else RED

    t = Table.grid(padding=(0, 1))
    t.add_column(style=DIM, justify="right")
    t.add_column()

    t.add_row("Patient",  "Sarah Johnson · PAT-001")
    t.add_row("Trial",    "TRIAL-001 · GLP-1 Agonist")
    t.add_row("Result",   Text(overall, style=color))
    t.add_row("Criteria", str(len(result.get("criteriaEvaluations", []))) + " evaluated")
    t.add_row("Time",     f"{elapsed:.2f}s")
    t.add_row("Services", "Gateway  →  KB  →  Bedrock")

    return Panel(
        t,
        title="[bold]Scenario 1 — Patient Eligibility[/bold]",
        border_style="deep_sky_blue1",
        padding=(1, 2),
    )


def panel_adverse_event(result: dict, elapsed: float) -> Panel:
    grade   = result.get("severity_grade", 0)
    alert   = result.get("alert_generated", False)
    cases   = result.get("historical_cases", [])
    rec     = result.get("recommendation", "")[:60]
    g_color = RED if grade >= 3 else YELLOW if grade >= 2 else GREEN

    t = Table.grid(padding=(0, 1))
    t.add_column(style=DIM, justify="right")
    t.add_column()

    t.add_row("Patient",          "Michael Chen · PAT-002")
    t.add_row("Event",            "Grade 3 Neutropenia · Day 14")
    t.add_row("Severity",         Text(f"Grade {grade}/5", style=g_color))
    t.add_row("Alert",            Text("YES ⚠", style=RED) if alert else Text("no", style=GREEN))
    t.add_row("Memory hits",      str(len(cases)))
    t.add_row("Recommendation",   rec + ("…" if len(result.get("recommendation","")) > 60 else ""))
    t.add_row("Time",             f"{elapsed:.2f}s")
    t.add_row("Services",         "Memory  →  Pattern matching")

    return Panel(
        t,
        title="[bold]Scenario 2 — Adverse Event[/bold]",
        border_style="magenta",
        padding=(1, 2),
    )


def panel_insurance(result: dict, elapsed: float) -> Panel:
    decision = result.get("decision", "unknown").replace("_", " ").upper()
    cost     = result.get("estimated_cost", 0)
    auth_id  = result.get("authorization_id", "N/A")
    policies = result.get("policy_evaluation", {})

    d_color = GREEN if "APPROVED" in decision else YELLOW if "REVIEW" in decision else RED

    t = Table.grid(padding=(0, 1))
    t.add_column(style=DIM, justify="right")
    t.add_column()

    t.add_row("Patient",   "PAT-001")
    t.add_row("Procedure", "CPT-80053 · Routine lab work")
    t.add_row("Amount",    f"${cost:,.0f}")
    t.add_row("Decision",  Text(decision, style=d_color))
    t.add_row("Auth ID",   auth_id)

    policy_text = Text()
    for name, passed in policies.items():
        sym   = "✓ " if passed else "✗ "
        color = "green" if passed else "red"
        policy_text.append(sym + name.replace("_", " "), style=color)
        policy_text.append("  ")
    t.add_row("Policies", policy_text)
    t.add_row("Time",     f"{elapsed:.2f}s")
    t.add_row("Services", "Verified Permissions (Cedar)")

    return Panel(
        t,
        title="[bold]Scenario 3 — Insurance Auth[/bold]",
        border_style="yellow",
        padding=(1, 2),
    )


def summary_table(results: list[tuple]) -> Table:
    t = Table(
        title="Clinical Operations Summary",
        box=box.ROUNDED,
        border_style="bright_white",
        header_style="bold cyan",
        show_lines=True,
        padding=(0, 1),
    )
    t.add_column("Scenario",        style="bold white",  min_width=28)
    t.add_column("Patient",         style="white",        min_width=18)
    t.add_column("Result",          justify="center",     min_width=22)
    t.add_column("AgentCore",       style=DIM,            min_width=28)
    t.add_column("Time",            justify="right",       min_width=7)

    label, result, elapsed = results[0]
    overall = result.get("overallEligibility", "?").upper()
    c = "bright_green" if overall == "ELIGIBLE" else "yellow"
    t.add_row("Patient Eligibility", "Sarah Johnson", Text(overall, style=f"bold {c}"),
              "Runtime + Gateway + KB", f"{elapsed:.2f}s")

    label, result, elapsed = results[1]
    grade = result.get("severity_grade", 0)
    g_c = "bright_red" if grade >= 3 else "yellow" if grade >= 2 else "bright_green"
    cases = len(result.get("historical_cases", []))
    t.add_row("Adverse Event", "Michael Chen",
              Text(f"Grade {grade}/5  ·  {cases} memory hit{'s' if cases != 1 else ''}", style=f"bold {g_c}"),
              "Runtime + Memory", f"{elapsed:.2f}s")

    label, result, elapsed = results[2]
    decision = result.get("decision", "?").replace("_", " ").upper()
    d_c = "bright_green" if "APPROVED" in decision else "yellow"
    t.add_row("Insurance Auth", "PAT-001 · $250",
              Text(decision, style=f"bold {d_c}"),
              "Runtime + Verified Permissions", f"{elapsed:.2f}s")

    return t


def main() -> None:
    console.print()
    console.print(Rule("[bold bright_white]MedFlow  ·  Amazon Bedrock AgentCore[/bold bright_white]",
                       style="bright_white"))
    console.print()
    console.print(Align.center(
        Text("Firing all three Runtime agents simultaneously…", style=DIM)
    ))
    console.print()

    tasks = [
        ("eligibility",   ELIGIBILITY_ARN,
         {"patient_id": "PAT-001", "trial_id": "TRIAL-001"}),
        ("adverse_event", ADVERSE_EVENT_ARN,
         {"patient_id": "PAT-002", "symptoms": ["neutropenia", "fatigue"],
          "medications": ["carboplatin", "MF-5120"],
          "timeline": "Grade 3 Neutropenia on Day 14, ANC 850",
          "store_outcome": True}),
        ("insurance_auth", INSURANCE_AUTH_ARN,
         {"patient_id": "PAT-001", "procedure_code": "CPT-80053",
          "procedure_description": "Routine lab work", "estimated_cost": 250}),
    ]

    results_map: dict[str, tuple] = {}

    with Progress(
        SpinnerColumn("dots2", style="deep_sky_blue1"),
        TextColumn("[bold]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_ids = {
            name: progress.add_task(f"{name.replace('_', ' ').title()}…", total=None)
            for name, _, _ in tasks
        }

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(_invoke, arn, payload): name
                for name, arn, payload in tasks
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result, elapsed = future.result()
                    results_map[name] = (name, result, elapsed)
                    progress.update(task_ids[name], description=f"[green]✓ {name.replace('_',' ').title()}")
                    progress.stop_task(task_ids[name])
                except Exception as exc:
                    results_map[name] = (name, {"error": str(exc)}, 0.0)
                    progress.update(task_ids[name], description=f"[red]✗ {name}")

    console.print()

    panels = [
        panel_eligibility(*results_map["eligibility"][1:]),
        panel_adverse_event(*results_map["adverse_event"][1:]),
        panel_insurance(*results_map["insurance_auth"][1:]),
    ]
    console.print(Columns(panels, equal=True, expand=True))
    console.print()

    ordered = [results_map["eligibility"], results_map["adverse_event"], results_map["insurance_auth"]]
    console.print(Align.center(summary_table(ordered)))

    console.print()
    total = sum(r[2] for r in ordered)
    console.print(Align.center(
        Text(f"Three agents  ·  Three AWS services  ·  {total:.2f}s total wall time",
             style="bold bright_white")
    ))
    console.print()
    console.print(Rule(style="bright_white"))
    console.print()


if __name__ == "__main__":
    main()
