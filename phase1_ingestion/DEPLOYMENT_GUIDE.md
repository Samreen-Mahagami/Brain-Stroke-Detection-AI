# Phase 1 Deployment Guide

## Prerequisites

### 1. AWS Account Setup
- Active AWS account
- AWS HealthImaging service enabled in your region
- Billing alerts configured (recommended)

### 2. Install AWS CLI
```bash
# Check if installed
aws --version

# If not installed:
# Linux/Mac
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Or use package manager
# Ubuntu/Debian
sudo apt install awscli

# Mac
brew install awscli
```

### 3. Configure AWS Credentials
```bash
aws configure

# Enter:
# AWS Access Key ID: [Your access key]
# AWS Secret Access Key: [Your secret key]
# Default region name: us-east-1 (or your preferred region)
# Default output format: json
```

### 4. Verify Configuration
```bash
# Check identity
aws sts get-caller-identity

# Should return:
# {
#     "UserId": "...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-user"
# }
```

## Deployment Steps

### Option 1: Automated Deployment (Recommended)

```bash
cd phase1_ingestion
./deploy.sh
```

This script will:
1. ✓ Validate AWS credentials
2. ✓ Validate CloudFormation template
3. ✓ Deploy infrastructure (S3, HealthImaging, DynamoDB, Lambda, API Gateway)
4. ✓ Package and deploy Lambda functions
5. ✓ Display stack outputs

**Expected Duration**: 3-5 minutes

### Option 2: Manual Deployment

#### Step 1: Deploy CloudFormation Stack
```bash
cd phase1_ingestion

aws cloudformation create-stack \
  --stack-name stroke-detection-phase1 \
  --template-body file://cloudformation_phase1.yaml \
  --parameters ParameterKey=ProjectName,ParameterValue=stroke-detection-ai \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

#### Step 2: Wait for Completion
```bash
aws cloudformation wait stack-create-complete \
  --stack-name stroke-detection-phase1 \
  --region us-east-1

# Check status
aws cloudformation describe-stacks \
  --stack-name stroke-detection-phase1 \
  --query 'Stacks[0].StackStatus'
```

#### Step 3: Deploy Lambda Functions
```bash
# Package upload handler
zip upload_handler.zip lambda_upload_handler.py

aws lambda update-function-code \
  --function-name stroke-detection-ai-upload-handler \
  --zip-file fileb://upload_handler.zip \
  --region us-east-1

# Package import monitor
zip import_monitor.zip lambda_import_monitor.py

aws lambda update-function-code \
  --function-name stroke-detection-ai-import-monitor \
  --zip-file fileb://import_monitor.zip \
  --region us-east-1
```

#### Step 4: Get Stack Outputs
```bash
aws cloudformation describe-stacks \
  --stack-name stroke-detection-phase1 \
  --query 'Stacks[0].Outputs'
```

## Verify Deployment

### 1. Check Resources Created
```bash
# S3 Bucket
aws s3 ls | grep stroke-detection

# HealthImaging Datastore
aws medical-imaging list-datastores

# DynamoDB Table
aws dynamodb list-tables | grep stroke-detection

# Lambda Functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `stroke-detection`)].FunctionName'

# API Gateway
aws apigatewayv2 get-apis --query 'Items[?Name==`stroke-detection-ai-api`]'
```

### 2. Test API Endpoint
```bash
# Get API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name stroke-detection-phase1 \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text)

echo $API_ENDPOINT

# Test (should return 400 - missing parameters, but proves API is working)
curl -X POST $API_ENDPOINT/upload \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Testing with Sample Data

### 1. Upload Test DICOM File
```bash
# Get bucket name
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name stroke-detection-phase1 \
  --query 'Stacks[0].Outputs[?OutputKey==`UploadBucket`].OutputValue' \
  --output text)

# Upload your DICOM file
aws s3 cp sample_brain_ct.dcm s3://$BUCKET/uploads/test_scan.dcm
```

### 2. Trigger Processing
```bash
curl -X POST $API_ENDPOINT/upload \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "TEST001",
    "study_description": "Brain CT - Test",
    "file_key": "uploads/test_scan.dcm"
  }'

# Response should include:
# {
#   "message": "DICOM ingestion started",
#   "study_id": "STUDY-xxxxxxxxxxxx",
#   "import_job_id": "...",
#   "status": "processing"
# }
```

### 3. Monitor Progress
```bash
# Check DynamoDB
aws dynamodb scan \
  --table-name stroke-detection-ai-study-metadata \
  --limit 5

# Check Step Functions
aws stepfunctions list-executions \
  --state-machine-arn $(aws cloudformation describe-stacks \
    --stack-name stroke-detection-phase1 \
    --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
    --output text)

# Check Lambda logs
aws logs tail /aws/lambda/stroke-detection-ai-upload-handler --follow
```

### 4. Run Automated Test
```bash
# Update test_upload.py with your values
python test_upload.py
```

## Troubleshooting

### Issue: "HealthImaging not available in region"
**Solution**: HealthImaging is only available in specific regions:
- us-east-1 (N. Virginia)
- us-west-2 (Oregon)
- eu-west-1 (Ireland)
- ap-southeast-2 (Sydney)

Change region in deploy.sh or use `--region` flag.

### Issue: "Access Denied" errors
**Solution**: Ensure your IAM user has these permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "iam:*",
        "lambda:*",
        "s3:*",
        "dynamodb:*",
        "medical-imaging:*",
        "apigateway:*",
        "states:*"
      ],
      "Resource": "*"
    }
  ]
}
```

### Issue: Stack creation fails
**Solution**: Check CloudFormation events:
```bash
aws cloudformation describe-stack-events \
  --stack-name stroke-detection-phase1 \
  --max-items 10
```

### Issue: Lambda deployment fails
**Solution**: Ensure Lambda functions exist first (created by CloudFormation), then deploy code.

## Cost Monitoring

### Set up billing alerts
```bash
# Create SNS topic for alerts
aws sns create-topic --name billing-alerts

# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:billing-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com
```

### Check current costs
```bash
# View cost and usage
aws ce get-cost-and-usage \
  --time-period Start=2025-10-01,End=2025-10-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://cost-filter.json
```

## Cleanup (Delete Everything)

```bash
# Delete CloudFormation stack (removes all resources)
aws cloudformation delete-stack \
  --stack-name stroke-detection-phase1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name stroke-detection-phase1

# Manually delete S3 bucket contents (if needed)
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name stroke-detection-phase1 \
  --query 'Stacks[0].Outputs[?OutputKey==`UploadBucket`].OutputValue' \
  --output text)

aws s3 rm s3://$BUCKET --recursive
```

## Next Steps

Once Phase 1 is deployed and tested:
1. ✓ DICOM files can be uploaded via API
2. ✓ Files are stored in HealthImaging
3. ✓ Metadata tracked in DynamoDB
4. ✓ Ready for Phase 2: Image Preprocessing

Proceed to Phase 2 deployment!
