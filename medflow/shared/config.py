"""Configuration management for MedFlow system.

Loads configuration from environment variables with validation.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AWSConfig(BaseSettings):
    """AWS service configuration."""

    region: str = Field(default="us-west-2", alias="AWS_REGION")
    account_id: str = Field(default="", alias="AWS_ACCOUNT_ID")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AgentCoreConfig(BaseSettings):
    """AgentCore Runtime configuration."""

    runtime_role_arn: str = Field(default="", alias="AGENTCORE_RUNTIME_ROLE_ARN")
    execution_timeout: int = Field(default=28800, alias="AGENTCORE_EXECUTION_TIMEOUT")
    memory_id: str = Field(default="", alias="AGENTCORE_MEMORY_ID")
    gateway_id: str = Field(default="", alias="AGENTCORE_GATEWAY_ID")
    gateway_url: str = Field(default="", alias="AGENTCORE_GATEWAY_URL")
    policy_store_id: str = Field(default="", alias="VERIFIED_PERMISSIONS_POLICY_STORE_ID")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class BedrockConfig(BaseSettings):
    """Bedrock Knowledge Base and model configuration."""

    knowledge_base_id: str = Field(
        default="PENDING_DEPLOYMENT", alias="BEDROCK_KNOWLEDGE_BASE_ID"
    )
    embedding_model: str = Field(
        default="amazon.titan-embed-text-v2:0", alias="BEDROCK_EMBEDDING_MODEL"
    )
    model_id: str = Field(
        default="anthropic.claude-3-5-haiku-20251022-v2:0", alias="BEDROCK_MODEL_ID"
    )
    opensearch_collection_id: str = Field(default="", alias="OPENSEARCH_COLLECTION_ID")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class LambdaConfig(BaseSettings):
    """Lambda function configuration."""

    pdf_generator_arn: str = Field(default="", alias="LAMBDA_PDF_GENERATOR_ARN")
    ehr_mock_arn: str = Field(default="", alias="LAMBDA_EHR_MOCK_ARN")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class S3Config(BaseSettings):
    """S3 bucket configuration."""

    generated_reports_bucket: str = Field(default="", alias="S3_GENERATED_REPORTS_BUCKET")
    trial_data_bucket: str = Field(default="", alias="S3_TRIAL_DATA_BUCKET")
    knowledge_base_bucket: str = Field(default="", alias="S3_KNOWLEDGE_BASE_BUCKET")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", alias="CLOUDWATCH_LOG_LEVEL"
    )
    cloudwatch_enabled: bool = Field(default=True, alias="CLOUDWATCH_ENABLED")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AppConfig(BaseSettings):
    """Application configuration."""

    environment: Literal["demo", "dev", "staging", "prod"] = Field(
        default="demo", alias="ENVIRONMENT"
    )
    debug: bool = Field(default=False, alias="DEBUG")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class MedFlowConfig(BaseSettings):
    """Complete MedFlow system configuration."""

    aws: AWSConfig = Field(default_factory=AWSConfig)
    agentcore: AgentCoreConfig = Field(default_factory=AgentCoreConfig)
    bedrock: BedrockConfig = Field(default_factory=BedrockConfig)
    lambda_: LambdaConfig = Field(default_factory=LambdaConfig)
    s3: S3Config = Field(default_factory=S3Config)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    app: AppConfig = Field(default_factory=AppConfig)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Global configuration instance
_config: MedFlowConfig | None = None


def get_config() -> MedFlowConfig:
    """Get the global configuration instance.

    Returns:
        MedFlowConfig instance loaded from environment variables
    """
    global _config
    if _config is None:
        _config = MedFlowConfig()
    return _config
