"""Logging configuration for MedFlow system.

Configures structured JSON logging with CloudWatch Logs integration
and audit trail support per FDA requirements (7-year retention).
"""

import logging
import sys
from typing import Any, Dict

from pythonjsonlogger import jsonlogger


class AuditLogFilter(logging.Filter):
    """Filter to identify audit-worthy log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Check if record should be sent to audit log."""
        return getattr(record, "audit", False)


class MedFlowFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for MedFlow logs."""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["agent"] = getattr(record, "agent", "unknown")

        # Add audit fields if present
        if hasattr(record, "audit") and record.audit:
            log_record["audit"] = True
            log_record["requester_id"] = getattr(record, "requester_id", None)
            log_record["tool_name"] = getattr(record, "tool_name", None)
            log_record["policy_decision"] = getattr(record, "policy_decision", None)


def configure_logging(
    agent_name: str,
    log_level: str = "INFO",
    enable_cloudwatch: bool = False,
) -> logging.Logger:
    """Configure logging for a MedFlow agent.

    Args:
        agent_name: Name of the agent (e.g., "orchestrator", "patient_eligibility")
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_cloudwatch: Whether to enable CloudWatch Logs handler

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(f"medflow.{agent_name}")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = MedFlowFormatter(
        "%(timestamp)s %(level)s %(agent)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S.%fZ",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Audit log handler (separate stream for audit events)
    audit_handler = logging.StreamHandler(sys.stderr)
    audit_handler.setLevel(logging.INFO)
    audit_handler.addFilter(AuditLogFilter())
    audit_handler.setFormatter(formatter)
    logger.addHandler(audit_handler)

    # CloudWatch handler (if enabled)
    if enable_cloudwatch:
        try:
            import watchtower

            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group=f"/aws/agentcore/medflow-{agent_name}",
                stream_name="{strftime:%Y-%m-%d}/{instance_id}",
                use_queues=True,
            )
            cloudwatch_handler.setLevel(logging.INFO)
            cloudwatch_handler.setFormatter(formatter)
            logger.addHandler(cloudwatch_handler)
        except ImportError:
            logger.warning("watchtower not installed, CloudWatch logging disabled")

    return logger


def log_audit_event(
    logger: logging.Logger,
    event_type: str,
    message: str,
    requester_id: str | None = None,
    tool_name: str | None = None,
    policy_decision: str | None = None,
    **kwargs: Any,
) -> None:
    """Log an audit event.

    Args:
        logger: Logger instance
        event_type: Type of audit event (e.g., "coordination_request", "tool_invocation")
        message: Human-readable message
        requester_id: ID of the user/system making the request
        tool_name: Name of tool being invoked (if applicable)
        policy_decision: Policy evaluation result (if applicable)
        **kwargs: Additional fields to include in audit log
    """
    extra = {
        "audit": True,
        "event_type": event_type,
        "requester_id": requester_id,
        "tool_name": tool_name,
        "policy_decision": policy_decision,
        **kwargs,
    }
    logger.info(message, extra=extra)
