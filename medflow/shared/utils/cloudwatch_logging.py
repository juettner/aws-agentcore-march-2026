"""CloudWatch Logs handler for AgentCore runtime agents.

Reads BEDROCK_AGENTCORE_LOG_GROUP from the environment (set via
update_agent_runtime environmentVariables) and attaches a watchtower
handler to the root logger so that all agent logging.info/warning/error
calls appear in the runtime's CloudWatch log group.
"""

import logging
import os


def setup_cloudwatch_logging(level: int = logging.INFO) -> None:
    """Attach a CloudWatch Logs handler to the root logger.

    No-ops silently if BEDROCK_AGENTCORE_LOG_GROUP is not set or if
    watchtower is unavailable, so local dev is unaffected.
    """
    log_group = os.environ.get("BEDROCK_AGENTCORE_LOG_GROUP")
    if not log_group:
        return

    try:
        import boto3
        import watchtower

        boto3_client = boto3.client(
            "logs",
            region_name=os.environ.get("AWS_REGION", "us-west-2"),
        )
        handler = watchtower.CloudWatchLogHandler(
            log_group_name=log_group,
            log_stream_name="application-logs",
            boto3_client=boto3_client,
            create_log_group=False,
            use_queues=False,  # synchronous — avoids background-thread flush issues
        )
        handler.setLevel(level)
        logging.getLogger().addHandler(handler)
        logging.getLogger(__name__).info(
            "CloudWatch logging enabled → %s", log_group
        )
    except ImportError:
        pass
    except Exception as exc:
        logging.warning("CloudWatch logging setup failed: %s", exc)
