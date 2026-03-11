#!/bin/bash
# Deploy Lambda functions for MedFlow demo
# Run this from the project root: ./infrastructure/deploy_lambdas.sh

set -e

REGION="${AWS_REGION:-us-west-2}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/MedFlowAgentCoreRuntimeRole"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Deploying MedFlow Lambda functions..."
echo "Region: $REGION"
echo ""

# --- EHR Mock API Lambda ---
echo "=== Deploying medflow-ehr-mock-api ==="
cd "$SCRIPT_DIR/lambda"

# Package EHR mock (no dependencies)
rm -f ehr_mock.zip
cp ehr_mock_lambda.py lambda_function.py
zip ehr_mock.zip lambda_function.py
rm lambda_function.py

if aws lambda get-function --function-name medflow-ehr-mock-api --region $REGION 2>/dev/null; then
    echo "Updating existing function..."
    aws lambda update-function-code \
        --function-name medflow-ehr-mock-api \
        --zip-file fileb://ehr_mock.zip \
        --region $REGION
else
    echo "Creating new function..."
    aws lambda create-function \
        --function-name medflow-ehr-mock-api \
        --runtime python3.12 \
        --role $ROLE_ARN \
        --handler lambda_function.lambda_handler \
        --zip-file fileb://ehr_mock.zip \
        --description "MedFlow mock EHR API for demo" \
        --timeout 15 \
        --memory-size 128 \
        --region $REGION \
        --tags Application=MedFlow,Environment=Demo
fi
echo "EHR Mock API deployed."
echo ""

# --- PDF Generator Lambda ---
echo "=== Deploying medflow-pdf-generator ==="
rm -rf /tmp/medflow-pdf-package
mkdir -p /tmp/medflow-pdf-package
pip install reportlab -t /tmp/medflow-pdf-package -q
cp pdf_generator.py /tmp/medflow-pdf-package/lambda_function.py
cd /tmp/medflow-pdf-package
rm -f "$SCRIPT_DIR/lambda/pdf_generator_deploy.zip"
zip -r9 "$SCRIPT_DIR/lambda/pdf_generator_deploy.zip" . -q

cd "$SCRIPT_DIR/lambda"
if aws lambda get-function --function-name medflow-pdf-generator --region $REGION 2>/dev/null; then
    echo "Updating existing function..."
    aws lambda update-function-code \
        --function-name medflow-pdf-generator \
        --zip-file fileb://pdf_generator_deploy.zip \
        --region $REGION
else
    echo "Creating new function..."
    aws lambda create-function \
        --function-name medflow-pdf-generator \
        --runtime python3.12 \
        --role $ROLE_ARN \
        --handler lambda_function.lambda_handler \
        --zip-file fileb://pdf_generator_deploy.zip \
        --description "MedFlow PDF report generator (FDA/EMA compliance)" \
        --timeout 60 \
        --memory-size 512 \
        --region $REGION \
        --tags Application=MedFlow,Environment=Demo
fi
echo "PDF Generator deployed."
echo ""

# Clean up
rm -rf /tmp/medflow-pdf-package
rm -f ehr_mock.zip

echo "=== Lambda Deployment Complete ==="
echo "EHR Mock API: arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:medflow-ehr-mock-api"
echo "PDF Generator: arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:medflow-pdf-generator"
