#!/bin/bash
# Quick setup script for real data implementation

set -e

echo "🚀 MedFlow Real Data Setup"
echo "=========================="
echo ""

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "venv" ]; then
        echo "📦 Activating virtual environment..."
        source venv/bin/activate
    else
        echo "⚠️  No virtual environment found. Creating one..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    fi
fi

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install it first."
    exit 1
fi

# Load environment (skip comments and empty lines)
if [ -f .env ]; then
    set -a
    source <(grep -v '^#' .env | grep -v '^$' | sed 's/\r$//')
    set +a
fi

AWS_REGION=${AWS_REGION:-us-east-1}
echo "📍 Region: $AWS_REGION"
echo ""

# Step 1: Create S3 bucket for trial data
echo "1️⃣  Setting up S3 bucket for trial data..."
if [ -z "$S3_TRIAL_DATA_BUCKET" ] || [ "$S3_TRIAL_DATA_BUCKET" = "medflow-trial-data" ]; then
    S3_TRIAL_DATA_BUCKET="medflow-trial-data-$(date +%s)"
    echo "   Creating bucket: $S3_TRIAL_DATA_BUCKET"
    
    if [ "$AWS_REGION" = "us-east-1" ]; then
        aws s3 mb s3://${S3_TRIAL_DATA_BUCKET} --region ${AWS_REGION} 2>/dev/null || echo "   Bucket may already exist"
    else
        aws s3 mb s3://${S3_TRIAL_DATA_BUCKET} --region ${AWS_REGION} --create-bucket-configuration LocationConstraint=${AWS_REGION} 2>/dev/null || echo "   Bucket may already exist"
    fi
    
    # Update .env file
    if grep -q "S3_TRIAL_DATA_BUCKET=" .env 2>/dev/null; then
        sed -i.bak "s|S3_TRIAL_DATA_BUCKET=.*|S3_TRIAL_DATA_BUCKET=${S3_TRIAL_DATA_BUCKET}|" .env
    else
        echo "S3_TRIAL_DATA_BUCKET=${S3_TRIAL_DATA_BUCKET}" >> .env
    fi
    echo "   ✅ Bucket created and added to .env"
else
    echo "   ✅ Using existing bucket: $S3_TRIAL_DATA_BUCKET"
fi
echo ""

# Step 2: Populate trial data
echo "2️⃣  Populating sample trial data..."
export S3_TRIAL_DATA_BUCKET
python3 infrastructure/scripts/populate_trial_data.py
echo ""

# Step 3: Set up Verified Permissions
echo "3️⃣  Setting up Amazon Verified Permissions..."
python3 infrastructure/scripts/setup_verified_permissions.py
echo ""

# Step 4: Summary
echo "✅ Setup Complete!"
echo ""
echo "📋 Configuration saved to .env"
echo ""
echo "🧪 Test the agents:"
echo ""
echo "# Test Regulatory Report Agent"
echo "python3 -c 'from medflow.agents.regulatory_report import RegulatoryReportAgent; from medflow.shared.models.regulatory import RegulatoryReportRequest; agent = RegulatoryReportAgent(); print(agent.generate(RegulatoryReportRequest(\"IND_Safety\", \"TRIAL-001\", \"2025-01-01\", \"2025-12-31\")))'"
echo ""
echo "# Test Insurance Authorization Agent"
echo "python3 -c 'from medflow.agents.insurance_auth import InsuranceAuthorizationAgent; from medflow.shared.models.authorization import AuthorizationRequest; agent = InsuranceAuthorizationAgent(); print(agent.authorize(AuthorizationRequest(\"PAT-001\", \"PROC-001\", \"Test\", 1500.0, \"PROV-001\")))'"
echo ""
echo "📚 Full documentation: docs/real-data-setup.md"
