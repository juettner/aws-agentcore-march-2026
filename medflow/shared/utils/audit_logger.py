import json
import csv
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    COORDINATION_REQUEST = "coordination_request"
    TOOL_INVOCATION = "tool_invocation"
    POLICY_EVALUATION = "policy_evaluation"
    AUTHENTICATION = "authentication"


class AuditLogger:
    """Comprehensive audit logging with 7-year retention."""
    
    def __init__(self, log_dir: str = "audit_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.retention_days = 2555  # 7 years
        
    def log_coordination_request(
        self,
        request_id: str,
        requester_identity: Dict[str, str],
        request_type: str,
        payload: Dict[str, Any]
    ):
        """Log coordination request."""
        self._write_audit_log({
            "event_type": AuditEventType.COORDINATION_REQUEST.value,
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "requester_user_id": requester_identity.get("userId"),
            "requester_role": requester_identity.get("role"),
            "request_type": request_type,
            "payload_summary": self._summarize_payload(payload),
        })
    
    def log_tool_invocation(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Any,
        success: bool,
        duration_ms: float
    ):
        """Log tool invocation."""
        self._write_audit_log({
            "event_type": AuditEventType.TOOL_INVOCATION.value,
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "parameters": self._sanitize_parameters(parameters),
            "success": success,
            "duration_ms": duration_ms,
            "result_summary": str(result)[:200] if result else None,
        })
    
    def log_policy_evaluation(
        self,
        policy_name: str,
        principal: str,
        action: str,
        resource: str,
        decision: str,
        reason: str = None
    ):
        """Log policy evaluation."""
        self._write_audit_log({
            "event_type": AuditEventType.POLICY_EVALUATION.value,
            "timestamp": datetime.now().isoformat(),
            "policy_name": policy_name,
            "principal": principal,
            "action": action,
            "resource": resource,
            "decision": decision,
            "reason": reason,
        })
    
    def log_authentication(
        self,
        user_id: str,
        auth_method: str,
        success: bool,
        token_used: bool = False,
        ip_address: str = None
    ):
        """Log authentication attempt."""
        self._write_audit_log({
            "event_type": AuditEventType.AUTHENTICATION.value,
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "auth_method": auth_method,
            "success": success,
            "token_used": token_used,
            "ip_address": ip_address,
        })
    
    def _write_audit_log(self, log_entry: Dict[str, Any]):
        """Write audit log entry to file."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit_{date_str}.jsonl"
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry, default=str) + '\n')
    
    def export_to_json(self, start_date: datetime, end_date: datetime, output_file: str):
        """Export audit logs to JSON format."""
        logs = self._read_logs_in_range(start_date, end_date)
        
        with open(output_file, 'w') as f:
            json.dump(logs, f, indent=2, default=str)
        
        logger.info(f"Exported {len(logs)} audit logs to {output_file}")
    
    def export_to_csv(self, start_date: datetime, end_date: datetime, output_file: str):
        """Export audit logs to CSV format."""
        logs = self._read_logs_in_range(start_date, end_date)
        
        if not logs:
            return
        
        fieldnames = set()
        for log in logs:
            fieldnames.update(log.keys())
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
            writer.writeheader()
            writer.writerows(logs)
        
        logger.info(f"Exported {len(logs)} audit logs to {output_file}")
    
    def _read_logs_in_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Read all audit logs within date range."""
        logs = []
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            log_file = self.log_dir / f"audit_{date_str}.jsonl"
            
            if log_file.exists():
                with open(log_file, 'r') as f:
                    for line in f:
                        logs.append(json.loads(line))
            
            current_date = current_date + timedelta(days=1)
        
        return logs
    
    def _summarize_payload(self, payload: Dict[str, Any]) -> str:
        """Create summary of payload for logging."""
        return json.dumps(payload, default=str)[:500]
    
    def _sanitize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from parameters."""
        sanitized = parameters.copy()
        sensitive_keys = ['password', 'token', 'secret', 'api_key']
        
        for key in sensitive_keys:
            if key in sanitized:
                sanitized[key] = "***REDACTED***"
        
        return sanitized
