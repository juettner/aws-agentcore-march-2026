#!/bin/bash

set -e

# ============================================================================
# MedFlow EHR Gateway - Comprehensive Deployment Script
# ============================================================================
# This script deploys all infrastructure components for the MedFlow EHR system
# Run from your local machine with AWS credentials configured
# ============================================================================

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
REGION="${AWS_REGION:-us-west-2}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/MedFlowAgentCoreRuntimeRole"
GATEWAY_ID="${AGENTCORE_GATEWAY_ID:?AGENTCORE_GATEWAY_ID must be set in environment or .env}"
OPENSEARCH_COLLECTION_ID="${OPENSEARCH_COLLECTION_ID:?OPENSEARCH_COLLECTION_ID must be set in environment or .env}"
OPENSEARCH_COLLECTION_ARN="arn:aws:aoss:${REGION}:${ACCOUNT_ID}:collection/${OPENSEARCH_COLLECTION_ID}"
POLICY_STORE_ID="${VERIFIED_PERMISSIONS_POLICY_STORE_ID:?VERIFIED_PERMISSIONS_POLICY_STORE_ID must be set in environment or .env}"
MEMORY_ID="${AGENTCORE_MEMORY_ID:?AGENTCORE_MEMORY_ID must be set in environment or .env}"
KB_INDEX_NAME="medflow-kb-index"
KB_VECTOR_FIELD="embedding"
KB_TEXT_FIELD="text"
KB_METADATA_FIELD="metadata"
EMBEDDING_MODEL_ARN="arn:aws:bedrock:us-west-2::foundation-model/amazon.titan-embed-text-v2:0"
S3_BUCKET="medflow-knowledge-base-${ACCOUNT_ID}"
S3_KB_PREFIX="protocols"

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Temporary directories
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if AWS CLI is installed
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    log_success "AWS CLI is installed"
}

# Verify AWS credentials are configured
check_aws_credentials() {
    if ! aws sts get-caller-identity --region "$REGION" &> /dev/null; then
        log_error "AWS credentials are not configured properly"
        exit 1
    fi
    log_success "AWS credentials verified"
}

# Check if Lambda function exists
lambda_exists() {
    local function_name=$1
    if aws lambda get-function --function-name "$function_name" --region "$REGION" &> /dev/null; then
        return 0
    fi
    return 1
}

# Check if S3 bucket exists
bucket_exists() {
    local bucket_name=$1
    if aws s3 ls "s3://${bucket_name}" --region "$REGION" &> /dev/null; then
        return 0
    fi
    return 1
}

# Check OpenSearch Serverless collection status
check_collection_status() {
    local collection_id=$1
    local status=$(aws opensearchserverless batch-get-collection \
        --ids "$collection_id" \
        --region "$REGION" \
        --query 'collectionDetails[0].status' \
        --output text 2>/dev/null || echo "UNKNOWN")
    echo "$status"
}

# Create the OpenSearch vector index required by Bedrock Knowledge Base
create_opensearch_index() {
    local collection_id=$1

    local endpoint=$(aws opensearchserverless batch-get-collection \
        --ids "$collection_id" \
        --region "$REGION" \
        --query 'collectionDetails[0].collectionEndpoint' \
        --output text 2>/dev/null)

    if [ -z "$endpoint" ] || [ "$endpoint" = "None" ]; then
        log_error "Could not retrieve OpenSearch collection endpoint"
        return 1
    fi

    log_info "OpenSearch endpoint: $endpoint"

    # Export the current AWS credentials (works with env vars, profiles, SSO,
    # assumed roles, instance metadata — anything AWS CLI v2 supports)
    local creds_json
    creds_json=$(aws configure export-credentials --format json 2>/dev/null)
    if [ -z "$creds_json" ]; then
        log_error "aws configure export-credentials failed; ensure AWS CLI v2 is installed"
        return 1
    fi

    # Parse with python3 stdlib json (no boto3 needed)
    local access_key secret_key session_token
    access_key=$(python3 -c "import sys,json; print(json.load(sys.stdin)['AccessKeyId'])"     <<< "$creds_json")
    secret_key=$(python3 -c "import sys,json; print(json.load(sys.stdin)['SecretAccessKey'])" <<< "$creds_json")
    session_token=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('SessionToken',''))" <<< "$creds_json")

    local index_url="${endpoint}/${KB_INDEX_NAME}"
    local token_header=()
    if [ -n "$session_token" ]; then
        token_header=(-H "x-amz-security-token: ${session_token}")
    fi

    # Check if index already exists
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --aws-sigv4 "aws:amz:${REGION}:aoss" \
        --user "${access_key}:${secret_key}" \
        "${token_header[@]}" \
        "$index_url")

    if [ "$http_code" = "200" ]; then
        log_info "OpenSearch index '$KB_INDEX_NAME' already exists"
        return 0
    fi

    log_info "Creating OpenSearch index '$KB_INDEX_NAME'..."

    local index_body
    index_body=$(cat << INDEXEOF
{
    "settings": {"index": {"knn": true}},
    "mappings": {
        "properties": {
            "${KB_VECTOR_FIELD}": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {"name": "hnsw", "engine": "faiss"}
            },
            "${KB_TEXT_FIELD}":     {"type": "text"},
            "${KB_METADATA_FIELD}": {"type": "text"}
        }
    }
}
INDEXEOF
)

    local resp_body resp_file
    resp_file=$(mktemp)
    http_code=$(curl -s -o "$resp_file" -w "%{http_code}" -XPUT \
        --aws-sigv4 "aws:amz:${REGION}:aoss" \
        --user "${access_key}:${secret_key}" \
        "${token_header[@]}" \
        -H "Content-Type: application/json" \
        -d "$index_body" \
        "$index_url")
    resp_body=$(cat "$resp_file"); rm -f "$resp_file"

    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        log_success "OpenSearch index '$KB_INDEX_NAME' created"
    else
        log_error "Failed to create OpenSearch index (HTTP $http_code): $resp_body"
        return 1
    fi
}

# Wait for OpenSearch collection to be active
wait_for_collection() {
    local collection_id=$1
    local max_attempts=60
    local attempt=0

    log_info "Waiting for OpenSearch Serverless collection to be ACTIVE..."

    while [ $attempt -lt $max_attempts ]; do
        local status=$(check_collection_status "$collection_id")

        if [ "$status" = "ACTIVE" ]; then
            log_success "OpenSearch Serverless collection is ACTIVE"
            return 0
        fi

        log_info "Collection status: $status (attempt $((attempt+1))/$max_attempts)"
        sleep 10
        ((attempt++))
    done

    log_error "Timeout waiting for OpenSearch Serverless collection to be ACTIVE"
    return 1
}

# ============================================================================
# Stage 1: Pre-flight Checks
# ============================================================================

stage_preflight_checks() {
    log_info "=========================================="
    log_info "Stage 1: Pre-flight Checks"
    log_info "=========================================="

    check_aws_cli
    check_aws_credentials

    log_success "Pre-flight checks completed"
}

# ============================================================================
# Stage 2: Deploy Lambda Functions
# ============================================================================

stage_deploy_lambdas() {
    log_info "=========================================="
    log_info "Stage 2: Deploy Lambda Functions"
    log_info "=========================================="

    # Deploy medflow-ehr-mock-api
    log_info "Deploying medflow-ehr-mock-api..."
    deploy_lambda_simple "medflow-ehr-mock-api" "$SCRIPT_DIR/lambda/ehr_mock_lambda.py"

    # Deploy medflow-pdf-generator
    log_info "Deploying medflow-pdf-generator..."
    deploy_lambda_with_deps "medflow-pdf-generator" "$SCRIPT_DIR/lambda/pdf_generator.py" "reportlab"

    log_success "Lambda functions deployed"
}

# Deploy Lambda function without dependencies (simple)
deploy_lambda_simple() {
    local function_name=$1
    local handler_file=$2

    if ! [ -f "$handler_file" ]; then
        log_error "Handler file not found: $handler_file"
        return 1
    fi

    # Create deployment package — Lambda expects lambda_function.py as handler
    local zip_file="$TEMP_DIR/${function_name}.zip"
    local pkg_dir="$TEMP_DIR/${function_name}_simple"
    mkdir -p "$pkg_dir"
    cp "$handler_file" "$pkg_dir/lambda_function.py"
    cd "$pkg_dir"
    zip -q "$zip_file" lambda_function.py
    cd - > /dev/null

    # Deploy or update Lambda function
    if lambda_exists "$function_name"; then
        log_info "$function_name already exists, updating code..."
        aws lambda update-function-code \
            --function-name "$function_name" \
            --zip-file "fileb://$zip_file" \
            --region "$REGION" > /dev/null
    else
        log_info "$function_name does not exist, creating..."
        aws lambda create-function \
            --function-name "$function_name" \
            --runtime python3.12 \
            --role "$ROLE_ARN" \
            --handler "lambda_function.lambda_handler" \
            --zip-file "fileb://$zip_file" \
            --timeout 15 \
            --memory-size 128 \
            --description "MedFlow mock EHR API for demo" \
            --region "$REGION" \
            --tags Application=MedFlow,Environment=Demo > /dev/null
    fi

    log_success "Deployed $function_name"
}

# Deploy Lambda function with dependencies
deploy_lambda_with_deps() {
    local function_name=$1
    local handler_file=$2
    local dependencies=$3

    if ! [ -f "$handler_file" ]; then
        log_error "Handler file not found: $handler_file"
        return 1
    fi

    # Create deployment package directory
    local pkg_dir="$TEMP_DIR/${function_name}_pkg"
    mkdir -p "$pkg_dir"

    # Copy handler file as lambda_function.py
    cp "$handler_file" "$pkg_dir/lambda_function.py"

    # Install dependencies
    if [ ! -z "$dependencies" ]; then
        log_info "Installing dependencies: $dependencies"
        pip install -q -t "$pkg_dir" $dependencies
    fi

    # Create zip file
    local zip_file="$TEMP_DIR/${function_name}.zip"
    cd "$pkg_dir"
    zip -r -q "$zip_file" .
    cd - > /dev/null

    # Deploy or update Lambda function
    if lambda_exists "$function_name"; then
        log_info "$function_name already exists, updating code..."
        aws lambda update-function-code \
            --function-name "$function_name" \
            --zip-file "fileb://$zip_file" \
            --region "$REGION" > /dev/null
    else
        log_info "$function_name does not exist, creating..."
        aws lambda create-function \
            --function-name "$function_name" \
            --runtime python3.12 \
            --role "$ROLE_ARN" \
            --handler "lambda_function.lambda_handler" \
            --zip-file "fileb://$zip_file" \
            --timeout 60 \
            --memory-size 512 \
            --description "MedFlow PDF report generator (FDA/EMA compliance)" \
            --region "$REGION" \
            --tags Application=MedFlow,Environment=Demo > /dev/null
    fi

    log_success "Deployed $function_name"
}

# ============================================================================
# Stage 3: Upload Knowledge Base Documents to S3
# ============================================================================

stage_upload_kb_docs() {
    log_info "=========================================="
    log_info "Stage 3: Upload Knowledge Base Documents"
    log_info "=========================================="

    local kb_docs_dir="$SCRIPT_DIR/kb-docs"

    if ! [ -d "$kb_docs_dir" ]; then
        log_warning "Knowledge base documents directory not found: $kb_docs_dir"
        return
    fi

    # Ensure bucket exists
    if ! bucket_exists "$S3_BUCKET"; then
        log_info "Creating S3 bucket: $S3_BUCKET"
        aws s3 mb "s3://${S3_BUCKET}" --region "$REGION"
        log_success "S3 bucket created"
    fi

    # Upload documents
    log_info "Uploading documents from $kb_docs_dir to s3://${S3_BUCKET}/${S3_KB_PREFIX}/"
    aws s3 sync "$kb_docs_dir" "s3://${S3_BUCKET}/${S3_KB_PREFIX}/" \
        --region "$REGION" \
        --delete

    log_success "Knowledge base documents uploaded"
}

# ============================================================================
# Stage 4: Wait for OpenSearch Collection and Create Knowledge Base
# ============================================================================

stage_create_knowledge_base() {
    log_info "=========================================="
    log_info "Stage 4: Create Bedrock Knowledge Base"
    log_info "=========================================="

    # Wait for collection to be active
    wait_for_collection "$OPENSEARCH_COLLECTION_ID"

    # Create the vector index before Bedrock tries to validate it
    create_opensearch_index "$OPENSEARCH_COLLECTION_ID"

    # Check if knowledge base already exists
    local kb_name="medflow-ehr-knowledge-base"
    local existing_kb=$(aws bedrock-agent list-knowledge-bases \
        --region "$REGION" \
        --query "knowledgeBaseSummaries[?name=='${kb_name}'].knowledgeBaseId" \
        --output text 2>/dev/null || echo "")

    if [ ! -z "$existing_kb" ]; then
        log_info "Knowledge base already exists: $existing_kb"
        KB_ID="$existing_kb"
    else
        log_info "Creating knowledge base..."

        # Create the knowledge base with proper separate configs
        local kb_config='{"type":"VECTOR","vectorKnowledgeBaseConfiguration":{"embeddingModelArn":"'"${EMBEDDING_MODEL_ARN}"'"}}'

        local storage_config='{"type":"OPENSEARCH_SERVERLESS","opensearchServerlessConfiguration":{"collectionArn":"'"${OPENSEARCH_COLLECTION_ARN}"'","vectorIndexName":"'"${KB_INDEX_NAME}"'","fieldMapping":{"vectorField":"'"${KB_VECTOR_FIELD}"'","textField":"'"${KB_TEXT_FIELD}"'","metadataField":"'"${KB_METADATA_FIELD}"'"}}}'

        KB_ID=$(aws bedrock-agent create-knowledge-base \
            --name "$kb_name" \
            --description "MedFlow clinical trial protocols and adverse event guidelines" \
            --role-arn "$ROLE_ARN" \
            --knowledge-base-configuration "$kb_config" \
            --storage-configuration "$storage_config" \
            --region "$REGION" \
            --query 'knowledgeBase.knowledgeBaseId' \
            --output text)

        log_success "Knowledge base created: $KB_ID"
    fi

    # Create or update data source
    log_info "Creating data source for S3 bucket..."

    local existing_datasource=$(aws bedrock-agent list-data-sources \
        --knowledge-base-id "$KB_ID" \
        --region "$REGION" \
        --query "dataSourceSummaries[0].dataSourceId" \
        --output text 2>/dev/null || echo "")

    if [ ! -z "$existing_datasource" ] && [ "$existing_datasource" != "None" ]; then
        log_info "Data source already exists: $existing_datasource"
        DATA_SOURCE_ID="$existing_datasource"
    else
        log_info "Creating new data source..."

        local ds_config='{"type":"S3","s3Configuration":{"bucketArn":"arn:aws:s3:::'"${S3_BUCKET}"'"}}'

        DATA_SOURCE_ID=$(aws bedrock-agent create-data-source \
            --knowledge-base-id "$KB_ID" \
            --name "medflow-clinical-protocols" \
            --description "Clinical trial protocols and adverse event guidelines from S3" \
            --data-source-configuration "$ds_config" \
            --region "$REGION" \
            --query 'dataSource.dataSourceId' \
            --output text)

        log_success "Data source created: $DATA_SOURCE_ID"
    fi

    # Start ingestion job
    log_info "Starting data source sync job..."

    local ingestion_job=$(aws bedrock-agent start-ingestion-job \
        --knowledge-base-id "$KB_ID" \
        --data-source-id "$DATA_SOURCE_ID" \
        --region "$REGION" \
        --query 'ingestionJob.ingestionJobId' \
        --output text)

    log_success "Ingestion job started: $ingestion_job"
    log_info "Note: Ingestion may take several minutes. You can check status with:"
    log_info "  aws bedrock-agent get-ingestion-job --knowledge-base-id $KB_ID --data-source-id $DATA_SOURCE_ID --ingestion-job-id $ingestion_job --region $REGION"
}

# ============================================================================
# Stage 5: Create Gateway Target
# ============================================================================

stage_create_gateway_target() {
    log_info "=========================================="
    log_info "Stage 5: Create Gateway Target"
    log_info "=========================================="

    local target_name="medflow-ehr-api"

    # Get Lambda function ARN
    local lambda_arn=$(aws lambda get-function \
        --function-name "medflow-ehr-mock-api" \
        --region "$REGION" \
        --query 'Configuration.FunctionArn' \
        --output text)

    if [ -z "$lambda_arn" ]; then
        log_error "Could not retrieve Lambda function ARN for medflow-ehr-mock-api"
        return 1
    fi

    log_info "Lambda function ARN: $lambda_arn"

    # Check if target already exists on the gateway
    local existing_targets=$(aws bedrock-agentcore-control list-gateway-targets \
        --gateway-identifier "$GATEWAY_ID" \
        --region "$REGION" \
        --query "targets[?name=='${target_name}'].targetId" \
        --output text 2>/dev/null || echo "")

    if [ ! -z "$existing_targets" ] && [ "$existing_targets" != "None" ]; then
        log_info "Gateway target already exists: $existing_targets"
        return
    fi

    log_info "Creating gateway target: $target_name"

    # Create the gateway target using AgentCore Gateway API
    # This creates a Lambda-backed MCP target with 5 tools
    local target_config_file="$TEMP_DIR/target_config.json"
    cat > "$target_config_file" << TARGETEOF
{
    "mcp": {
        "lambda": {
            "lambdaArn": "${lambda_arn}",
            "toolSchema": {
                "inlinePayload": [
                    {
                        "name": "get_patient_record",
                        "description": "Get patient demographic and medical record by patient ID",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "patientId": {"type": "string", "description": "Patient identifier (e.g., PAT-001)"}
                            },
                            "required": ["patientId"]
                        }
                    },
                    {
                        "name": "get_lab_results",
                        "description": "Get laboratory test results for a patient",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "patientId": {"type": "string", "description": "Patient identifier"}
                            },
                            "required": ["patientId"]
                        }
                    },
                    {
                        "name": "get_adverse_events",
                        "description": "Get reported adverse events for a patient",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "patientId": {"type": "string", "description": "Patient identifier"}
                            },
                            "required": ["patientId"]
                        }
                    },
                    {
                        "name": "submit_insurance_auth",
                        "description": "Submit an insurance authorization request",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "patientId": {"type": "string", "description": "Patient identifier"},
                                "procedureCode": {"type": "string", "description": "CPT procedure code"},
                                "amount": {"type": "number", "description": "Requested authorization amount in USD"},
                                "description": {"type": "string", "description": "Description of procedure/treatment"}
                            },
                            "required": ["patientId", "amount", "description"]
                        }
                    },
                    {
                        "name": "list_patients",
                        "description": "List all patients in the EHR system",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            }
        }
    }
}
TARGETEOF

    aws bedrock-agentcore-control create-gateway-target \
        --gateway-identifier "$GATEWAY_ID" \
        --name "$target_name" \
        --target-configuration "file://$target_config_file" \
        --credential-provider-configurations '[{"credentialProviderType":"GATEWAY_IAM_ROLE"}]' \
        --region "$REGION" > /dev/null

    log_success "Gateway target created: $target_name"
}

# ============================================================================
# Stage 6: Write Environment File
# ============================================================================

stage_write_env_file() {
    log_info "=========================================="
    log_info "Stage 6: Write Environment File"
    log_info "=========================================="

    local env_file="$PROJECT_ROOT/.env"

    log_info "Writing environment variables to $env_file"

    cat > "$env_file" << EOF
# MedFlow Environment Configuration
# Generated by deploy_all.sh on $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# AWS Configuration
AWS_REGION=${REGION}
AWS_ACCOUNT_ID=${ACCOUNT_ID}

# AgentCore Runtime
AGENTCORE_RUNTIME_ROLE_ARN=${ROLE_ARN}
AGENTCORE_EXECUTION_TIMEOUT=28800

# AgentCore Memory
AGENTCORE_MEMORY_ID=${MEMORY_ID}

# AgentCore Gateway
AGENTCORE_GATEWAY_ID=${GATEWAY_ID}
AGENTCORE_GATEWAY_URL=https://${GATEWAY_ID}.gateway.bedrock-agentcore.${REGION}.amazonaws.com/mcp

# Verified Permissions
VERIFIED_PERMISSIONS_POLICY_STORE_ID=${POLICY_STORE_ID}

# Bedrock Configuration
BEDROCK_KNOWLEDGE_BASE_ID=${KB_ID:-PENDING_DEPLOYMENT}
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
BEDROCK_MODEL_ID=anthropic.claude-3-5-haiku-20251022-v2:0
OPENSEARCH_COLLECTION_ID=${OPENSEARCH_COLLECTION_ID}

# Lambda Functions
LAMBDA_PDF_GENERATOR_ARN=arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:medflow-pdf-generator
LAMBDA_EHR_MOCK_ARN=arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:medflow-ehr-mock-api

# S3 Buckets
S3_GENERATED_REPORTS_BUCKET=medflow-generated-reports-${ACCOUNT_ID}
S3_TRIAL_DATA_BUCKET=medflow-trial-data-1771945071
S3_KNOWLEDGE_BASE_BUCKET=medflow-knowledge-base-${ACCOUNT_ID}

# Logging & Application
CLOUDWATCH_LOG_LEVEL=INFO
CLOUDWATCH_ENABLED=true
ENVIRONMENT=demo
DEBUG=false
EOF

    log_success "Environment file written to $env_file"
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    log_info "=========================================="
    log_info "MedFlow EHR Gateway Deployment"
    log_info "=========================================="
    log_info "Region: $REGION"
    log_info "Account: $ACCOUNT_ID"
    log_info "Gateway ID: $GATEWAY_ID"
    log_info ""

    stage_preflight_checks
    log_info ""

    stage_deploy_lambdas
    log_info ""

    stage_upload_kb_docs
    log_info ""

    stage_create_knowledge_base
    log_info ""

    stage_create_gateway_target
    log_info ""

    stage_write_env_file
    log_info ""

    log_success "=========================================="
    log_success "Deployment completed successfully!"
    log_success "=========================================="
    log_info ""
    log_info "Summary of deployed resources:"
    log_info "  - Lambda functions: medflow-ehr-mock-api, medflow-pdf-generator"
    log_info "  - S3 bucket: $S3_BUCKET"
    log_info "  - Knowledge base: $KB_ID"
    log_info "  - Gateway target: medflow-ehr-api"
    log_info ""
    log_info "Configuration saved to: $PROJECT_ROOT/.env"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Verify Lambda functions are deployed: aws lambda list-functions --region $REGION"
    log_info "  2. Check KB ingestion status: aws bedrock-agent get-ingestion-job --knowledge-base-id $KB_ID --region $REGION"
    log_info "  3. Review .env file for all resource IDs"
}

# Execute main function
main "$@"
