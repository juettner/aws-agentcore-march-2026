#!/usr/bin/env python3
"""Simple test runner showing available tests."""

import subprocess
import sys

def run_command(cmd, description):
    """Run a command and show results."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0

def main():
    print("\n" + "="*60)
    print("  MedFlow Test Options")
    print("="*60)
    
    print("\n📋 Available Tests:\n")
    print("1. Unit Tests (no AWS required)")
    print("   pytest tests/unit/ -v")
    print()
    print("2. Property Tests (no AWS required)")
    print("   pytest tests/property/ -v")
    print()
    print("3. All Tests with Coverage")
    print("   pytest --cov=medflow")
    print()
    print("4. Specific Agent Tests")
    print("   pytest tests/unit/test_regulatory_report_agent.py -v")
    print("   pytest tests/unit/test_insurance_auth_agent.py -v")
    print()
    
    choice = input("Run which test? (1-4, or 'q' to quit): ").strip()
    
    if choice == '1':
        return run_command("pytest tests/unit/ -v", "Running Unit Tests")
    elif choice == '2':
        return run_command("pytest tests/property/ -v", "Running Property Tests")
    elif choice == '3':
        return run_command("pytest --cov=medflow --cov-report=term-missing", "Running All Tests with Coverage")
    elif choice == '4':
        print("\nWhich agent?")
        print("  a) Regulatory Report")
        print("  b) Insurance Authorization")
        print("  c) Patient Eligibility")
        print("  d) Orchestrator")
        agent = input("Choice (a-d): ").strip().lower()
        
        tests = {
            'a': "pytest tests/unit/test_regulatory_report_agent.py -v",
            'b': "pytest tests/unit/test_insurance_auth_agent.py -v",
            'c': "pytest tests/unit/test_patient_eligibility.py -v",
            'd': "pytest tests/unit/test_orchestrator.py -v",
        }
        
        if agent in tests:
            return run_command(tests[agent], f"Running {agent.upper()} Tests")
        else:
            print("Invalid choice")
            return False
    elif choice.lower() == 'q':
        print("Exiting...")
        return True
    else:
        print("Invalid choice")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
