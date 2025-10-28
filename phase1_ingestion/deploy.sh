#!/bin/bash

# Phase 1 Deployment Script
# Brain Stroke Detection AI - DICOM Ingestion & Storage

set -e

echo "=========================================="
echo "Phase 1: DICOM Ingestion Deployment"
echo "=========================================="
echo ""

# Configuration
STACK_NAME="stroke-detection-phase1"
PROJECT_NAME="stroke-detection-ai"
REGION=${AWS_REGION:-us-east-1}

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

# Check AWS credentials
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}✗ AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ AWS Account: ${ACCOUNT_ID}${NC}"
echo ""

# Validate CloudFormation template
echo "Validating CloudFormation template..."
if aws cloudformation validate-template \
    --template-body file://cloudformation_phase1.yaml \
    --region $REGION &> /dev/null; then
    echo -e "${GREEN}✓ Template is valid${NC}"
else
    echo -e "${RED}✗ Template validation failed${NC}"
    exit 1
fi
echo ""

# Check if stack exists
if aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION &> /dev/null; then
    echo -e "${YELLOW}Stack already exists. Updating...${NC}"
    OPERATION="update-stack"
else
    echo "Creating new stack..."
    OPERATION="create-stack"
fi

# Deploy stack
echo "Deploying infrastructure..."
aws cloudformation $OPERATION \
    --stack-name $STACK_NAME \
    --template-body file://cloudformation_phase1.yaml \
    --parameters ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION

echo ""
echo "Waiting for stack operation to complete..."
echo "(This may take 3-5 minutes)"

if [ "$OPERATION" = "create-stack" ]; then
    aws cloudformation wait stack-create-complete \
        --stack-name $STACK_NAME \
        --region $REGION
else
    aws cloudformation wait stack-update-complete \
        --stack-name $STACK_NAME \
        --region $REGION 2>/dev/null || true
fi

echo -e "${GREEN}✓ Stack deployment complete${NC}"
echo ""

# Get outputs
echo "=========================================="
echo "Stack Outputs:"
echo "=========================================="
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

# Package and deploy Lambda functions
echo ""
echo "=========================================="
echo "Deploying Lambda Functions"
echo "=========================================="

# Upload Handler
echo "Packaging upload handler..."
cd "$(dirname "$0")"
zip -q upload_handler.zip lambda_upload_handler.py
UPLOAD_FUNCTION="${PROJECT_NAME}-upload-handler"

echo "Deploying upload handler..."
aws lambda update-function-code \
    --function-name $UPLOAD_FUNCTION \
    --zip-file fileb://upload_handler.zip \
    --region $REGION > /dev/null

echo -e "${GREEN}✓ Upload handler deployed${NC}"

# Import Monitor
echo "Packaging import monitor..."
zip -q import_monitor.zip lambda_import_monitor.py
MONITOR_FUNCTION="${PROJECT_NAME}-import-monitor"

echo "Deploying import monitor..."
aws lambda update-function-code \
    --function-name $MONITOR_FUNCTION \
    --zip-file fileb://import_monitor.zip \
    --region $REGION > /dev/null

echo -e "${GREEN}✓ Import monitor deployed${NC}"

# Cleanup
rm -f upload_handler.zip import_monitor.zip

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Phase 1 Deployment Complete!${NC}"
echo "=========================================="
echo ""

# Get API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text)

UPLOAD_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`UploadBucket`].OutputValue' \
    --output text)

echo "Next Steps:"
echo "1. Upload a DICOM file to S3:"
echo "   aws s3 cp your_scan.dcm s3://${UPLOAD_BUCKET}/uploads/"
echo ""
echo "2. Trigger processing:"
echo "   curl -X POST ${API_ENDPOINT}/upload \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"patient_id\": \"P123456\", \"file_key\": \"uploads/your_scan.dcm\"}'"
echo ""
echo "3. Or run the test script:"
echo "   python test_upload.py"
echo ""
