#!/bin/bash
# Deployment script for MedFlow infrastructure
# This is a tech demo using a single AWS environment

set -e

echo "MedFlow Infrastructure Deployment"
echo "=================================="
echo ""

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed"
    exit 1
fi

# Check AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS credentials are not configured"
    echo "Run: aws configure"
    exit 1
fi

REGION=${AWS_REGION:-us-east-1}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Deploying to AWS Account: $ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# Create IAM role for AgentCore Runtime
echo "Creating IAM role for AgentCore Runtime..."
ROLE_NAME="MedFlowAgentCoreRuntimeRole"

if aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
    echo "Role $ROLE_NAME already exists, skipping creation"
else
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file://infrastructure/iam/agentcore-runtime-role.json \
        --description "IAM role for MedFlow AgentCore Runtime" \
        --tags Key=Application,Value=MedFlow Key=Environment,Value=Demo
    echo "Created role: $ROLE_NAME"
fi

# Attach policy to role
echo "Attaching policy to role..."
POLICY_NAME="MedFlowAgentCoreRuntimePolicy"

# Check if policy exists
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"
if aws iam get-policy --policy-arn $POLICY_ARN &> /dev/null; then
    echo "Policy $POLICY_NAME already exists"
    # Create new policy version
    aws iam create-policy-version \
        --policy-arn $POLICY_ARN \
        --policy-document file://infrastructure/iam/agentcore-runtime-policy.json \
        --set-as-default
    echo "Updated policy version"
else
    # Create new policy
    aws iam create-policy \
        --policy-name $POLICY_NAME \
        --policy-document file://infrastructure/iam/agentcore-runtime-policy.json \
        --description "IAM policy for MedFlow AgentCore Runtime"
    echo "Created policy: $POLICY_NAME"
fi

# Attach policy to role
aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn $POLICY_ARN
echo "Attached policy to role"

# Create CloudWatch Log Groups
echo ""
echo "Creating CloudWatch Log Groups..."

LOG_GROUPS=(
    "/aws/agentcore/medflow-orchestrator"
    "/aws/agentcore/medflow-patient-eligibility"
    "/aws/agentcore/medflow-adverse-event"
    "/aws/agentcore/medflow-regulatory-report"
    "/aws/agentcore/medflow-insurance-auth"
    "/aws/agentcore/medflow-patient-comm"
    "/aws/agentcore/medflow-trial-coordinator"
    "/aws/agentcore/medflow-audit"
)

for LOG_GROUP in "${LOG_GROUPS[@]}"; do
    if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region $REGION | grep -q "$LOG_GROUP"; then
        echo "Log group $LOG_GROUP already exists"
    else
        aws logs create-log-group \
            --log-group-name "$LOG_GROUP" \
            --region $REGION
        
        # Set retention to 7 years (2557 days) per FDA requirements
        aws logs put-retention-policy \
            --log-group-name "$LOG_GROUP" \
            --retention-in-days 2557 \
            --region $REGION
        
        # Add tags
        aws logs tag-log-group \
            --log-group-name "$LOG_GROUP" \
            --tags Application=MedFlow,Environment=Demo,Compliance=FDA-7-Year-Retention \
            --region $REGION
        
        echo "Created log group: $LOG_GROUP"
    fi
done

echo ""
echo "Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Configure AWS AgentCore services (Knowledge Base, Memory, Gateway, Policy, Identity)"
echo "2. Set up Python virtual environment: python -m venv venv && source venv/bin/activate"
echo "3. Install dependencies: pip install -r requirements.txt"
echo "4. Run tests: pytest"
echo ""
echo "IAM Role ARN: arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
