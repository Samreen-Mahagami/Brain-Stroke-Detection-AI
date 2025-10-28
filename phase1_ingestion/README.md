# Phase 1: DICOM Ingestion & Storage

This phase handles secure upload, validation, and storage of brain CT/MRI DICOM files using AWS HealthImaging.

## Architecture

```
Patient/Clinician → API Gateway → Lambda (Upload Handler)
                                        ↓
                                   S3 Bucket
                                        ↓
                              AWS HealthImaging
                                        ↓
                                   DynamoDB
                                        ↓
                              Step Functions (Monitor)
```

## Components

### 1. **S3 Bucket** (`DicomUploadBucket`)
- Stores raw DICOM files temporarily
- Encrypted at rest (AES-256)
- Versioning enabled
- 90-day lifecycle policy

### 2. **AWS HealthImaging Datastore**
- HIPAA-compliant medical imaging storage
- Optimized for DICOM format
- Fast frame retrieval for AI processing
- Automatic metadata extraction

### 3. **DynamoDB Table** (`StudyMetadataTable`)
- Stores study metadata and processing status
- Primary key: `study_id`
- GSI: `patient_id` + `upload_timestamp`
- Tracks: patient info, import status, image set IDs

### 4. **Lambda Functions**

#### `lambda_upload_handler.py`
- **Trigger**: API Gateway POST request
- **Purpose**: Validate upload and start HealthImaging import
- **Actions**:
  - Validate patient_id and file_key
  - Generate unique study_id
  - Start HealthImaging import job
  - Save metadata to DynamoDB
  - Trigger Step Functions workflow

#### `lambda_import_monitor.py`
- **Trigger**: Step Functions (polling)
- **Purpose**: Check HealthImaging import job status
- **Actions**:
  - Query import job status
  - Update DynamoDB with progress
  - Extract image_set_id when complete
  - Return status to Step Functions

### 5. **Step Functions State Machine**
- Orchestrates import monitoring
- Polls every 30 seconds until complete
- Handles success/failure states
- Prepares for Phase 2 (preprocessing)

### 6. **API Gateway**
- HTTP API endpoint: `POST /upload`
- CORS enabled
- Integrates with Lambda upload handler

## Deployment

### Prerequisites
- AWS CLI configured
- AWS account with HealthImaging enabled
- Appropriate IAM permissions

### Deploy Infrastructure

```bash
# Deploy CloudFormation stack
aws cloudformation create-stack \
  --stack-name stroke-detection-phase1 \
  --template-body file://cloudformation_phase1.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters ParameterKey=ProjectName,ParameterValue=stroke-detection-ai

# Wait for stack creation
aws cloudformation wait stack-create-complete \
  --stack-name stroke-detection-phase1

# Get outputs
aws cloudformation describe-stacks \
  --stack-name stroke-detection-phase1 \
  --query 'Stacks[0].Outputs'
```

### Deploy Lambda Code

```bash
# Package upload handler
cd phase1_ingestion
zip -r upload_handler.zip lambda_upload_handler.py
aws lambda update-function-code \
  --function-name stroke-detection-ai-upload-handler \
  --zip-file fileb://upload_handler.zip

# Package import monitor
zip -r import_monitor.zip lambda_import_monitor.py
aws lambda update-function-code \
  --function-name stroke-detection-ai-import-monitor \
  --zip-file fileb://import_monitor.zip
```

## Usage

### Upload DICOM File

```bash
# 1. Upload DICOM to S3
aws s3 cp brain_scan.dcm s3://stroke-detection-ai-dicom-uploads-{ACCOUNT_ID}/uploads/

# 2. Trigger processing via API
curl -X POST https://{API_ID}.execute-api.{REGION}.amazonaws.com/prod/upload \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "P123456",
    "study_description": "Brain CT - Suspected Stroke",
    "file_key": "uploads/brain_scan.dcm"
  }'

# Response:
# {
#   "message": "DICOM ingestion started",
#   "study_id": "STUDY-abc123def456",
#   "import_job_id": "12345678901234567890123456789012",
#   "status": "processing"
# }
```

### Check Processing Status

```bash
# Query DynamoDB
aws dynamodb get-item \
  --table-name stroke-detection-ai-study-metadata \
  --key '{"study_id": {"S": "STUDY-abc123def456"}}'

# Check Step Functions execution
aws stepfunctions describe-execution \
  --execution-arn arn:aws:states:{REGION}:{ACCOUNT}:execution:stroke-detection-ai-processing:stroke-analysis-STUDY-abc123def456
```

## Data Flow

1. **Upload Request** → API Gateway receives POST with patient_id and file_key
2. **Validation** → Lambda verifies DICOM exists in S3
3. **Import Job** → HealthImaging starts DICOM import
4. **Metadata Storage** → DynamoDB stores study info with status "IMPORTING"
5. **Workflow Start** → Step Functions begins monitoring
6. **Polling Loop** → Lambda checks import status every 30s
7. **Completion** → When done, DynamoDB updated with image_set_id
8. **Ready** → Status changes to "READY_FOR_ANALYSIS" for Phase 2

## DynamoDB Schema

```json
{
  "study_id": "STUDY-abc123def456",
  "patient_id": "P123456",
  "upload_timestamp": "2025-10-28T14:30:00.000Z",
  "study_description": "Brain CT - Suspected Stroke",
  "s3_bucket": "stroke-detection-ai-dicom-uploads-123456789012",
  "s3_key": "uploads/brain_scan.dcm",
  "datastore_id": "1234567890abcdef1234567890abcdef",
  "import_job_id": "12345678901234567890123456789012",
  "image_set_id": "fedcba0987654321fedcba0987654321",
  "status": "READY_FOR_ANALYSIS",
  "import_status": "COMPLETED",
  "processing_stage": "ingestion"
}
```

## Monitoring

### CloudWatch Logs
- `/aws/lambda/stroke-detection-ai-upload-handler`
- `/aws/lambda/stroke-detection-ai-import-monitor`
- `/aws/states/stroke-detection-ai-processing`

### Metrics to Watch
- Lambda invocation count and errors
- HealthImaging import job duration
- DynamoDB read/write capacity
- Step Functions execution success rate

## Security

- **Encryption**: All data encrypted at rest (S3, DynamoDB, HealthImaging)
- **IAM**: Least privilege access for all services
- **VPC**: Can be deployed in VPC for additional isolation
- **HIPAA**: HealthImaging is HIPAA-eligible service
- **Audit**: CloudTrail logs all API calls

## Cost Estimation (per 1000 studies)

- **S3 Storage**: ~$0.50 (assuming 5MB per DICOM, 90-day retention)
- **HealthImaging**: ~$10 (storage + import jobs)
- **DynamoDB**: ~$0.25 (on-demand pricing)
- **Lambda**: ~$0.20 (minimal compute)
- **Step Functions**: ~$0.25 (state transitions)
- **API Gateway**: ~$0.10 (HTTP API requests)

**Total**: ~$11.30 per 1000 studies

## Next Steps

Once Phase 1 is complete:
- ✅ DICOM files stored in HealthImaging
- ✅ Metadata in DynamoDB
- ✅ Ready for Phase 2: Image Preprocessing & Retrieval

Proceed to `phase2_preprocessing/` for the next stage.
