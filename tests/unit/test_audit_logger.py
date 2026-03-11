import pytest
from datetime import datetime, timedelta
from pathlib import Path
import json

from medflow.shared.utils.audit_logger import AuditLogger, AuditEventType


@pytest.fixture
def audit_logger():
    return AuditLogger(log_dir=".test_audit_logs")


def test_log_coordination_request(audit_logger):
    """Test logging coordination request."""
    audit_logger.log_coordination_request(
        request_id="REQ-001",
        requester_identity={"userId": "user-1", "role": "coordinator"},
        request_type="patient_screening",
        payload={"patient_id": "P001", "trial_id": "T001"}
    )
    
    log_file = audit_logger.log_dir / f"audit_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    assert log_file.exists()
    
    with open(log_file, 'r') as f:
        log_entry = json.loads(f.readline())
    
    assert log_entry["event_type"] == AuditEventType.COORDINATION_REQUEST.value
    assert log_entry["request_id"] == "REQ-001"
    assert log_entry["requester_user_id"] == "user-1"


def test_log_tool_invocation(audit_logger):
    """Test logging tool invocation."""
    audit_logger.log_tool_invocation(
        tool_name="get_patient_record",
        parameters={"patient_id": "P001"},
        result={"name": "John Doe"},
        success=True,
        duration_ms=150.5
    )
    
    log_file = audit_logger.log_dir / f"audit_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
        log_entry = json.loads(lines[-1])
    
    assert log_entry["event_type"] == AuditEventType.TOOL_INVOCATION.value
    assert log_entry["tool_name"] == "get_patient_record"
    assert log_entry["success"] is True
    assert log_entry["duration_ms"] == 150.5


def test_log_policy_evaluation(audit_logger):
    """Test logging policy evaluation."""
    audit_logger.log_policy_evaluation(
        policy_name="insurance_authorization_policy",
        principal="user-1",
        action="submit_authorization",
        resource="authorization-001",
        decision="allow",
        reason="Cost under $500 threshold"
    )
    
    log_file = audit_logger.log_dir / f"audit_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
        log_entry = json.loads(lines[-1])
    
    assert log_entry["event_type"] == AuditEventType.POLICY_EVALUATION.value
    assert log_entry["decision"] == "allow"
    assert log_entry["reason"] == "Cost under $500 threshold"


def test_log_authentication(audit_logger):
    """Test logging authentication attempt."""
    audit_logger.log_authentication(
        user_id="user-1",
        auth_method="oauth",
        success=True,
        token_used=True,
        ip_address="192.168.1.1"
    )
    
    log_file = audit_logger.log_dir / f"audit_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
        log_entry = json.loads(lines[-1])
    
    assert log_entry["event_type"] == AuditEventType.AUTHENTICATION.value
    assert log_entry["user_id"] == "user-1"
    assert log_entry["success"] is True
    assert log_entry["token_used"] is True


def test_export_to_json(audit_logger):
    """Test exporting audit logs to JSON."""
    audit_logger.log_coordination_request(
        "REQ-001", {"userId": "user-1", "role": "admin"}, "test", {}
    )
    
    start_date = datetime.now() - timedelta(days=1)
    end_date = datetime.now() + timedelta(days=1)
    output_file = ".test_audit_logs/export.json"
    
    audit_logger.export_to_json(start_date, end_date, output_file)
    
    assert Path(output_file).exists()
    
    with open(output_file, 'r') as f:
        logs = json.load(f)
    
    assert len(logs) > 0
    assert logs[0]["event_type"] == AuditEventType.COORDINATION_REQUEST.value


def test_export_to_csv(audit_logger):
    """Test exporting audit logs to CSV."""
    audit_logger.log_tool_invocation(
        "test_tool", {"param": "value"}, "result", True, 100.0
    )
    
    start_date = datetime.now() - timedelta(days=1)
    end_date = datetime.now() + timedelta(days=1)
    output_file = ".test_audit_logs/export.csv"
    
    audit_logger.export_to_csv(start_date, end_date, output_file)
    
    assert Path(output_file).exists()


def test_parameter_sanitization(audit_logger):
    """Test sensitive parameter sanitization."""
    audit_logger.log_tool_invocation(
        "auth_tool",
        {"username": "user1", "password": "secret123", "api_key": "key123"},
        "success",
        True,
        50.0
    )
    
    log_file = audit_logger.log_dir / f"audit_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
        log_entry = json.loads(lines[-1])
    
    assert log_entry["parameters"]["password"] == "***REDACTED***"
    assert log_entry["parameters"]["api_key"] == "***REDACTED***"
    assert log_entry["parameters"]["username"] == "user1"
