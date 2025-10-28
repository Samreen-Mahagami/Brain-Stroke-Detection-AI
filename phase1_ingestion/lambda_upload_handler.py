"""
Lambda Function: DICOM Upload Handler
Triggered by: API Gateway POST request
Purpose: Validate and initiate DICOM ingestion to AWS HealthImaging
"""

import json
import boto3
import os
from datetime import datetime
import uuid

s3_client = boto3.client('s3')
healthimaging_client = boto3.client('medical-imaging')
dynamodb = boto3.resource('dynamodb')
sfn_client = boto3.client('stepfunctions')

# Environment variables
UPLOAD_BUCKET = os.environ['UPLOAD_BUCKET']
DATASTORE_ID = os.environ['HEALTHIMAGING_DATASTORE_ID']
METADATA_TABLE = os.environ['DYNAMODB_TABLE']
STEP_FUNCTION_ARN = os.environ['STEP_FUNCTION_ARN']

def lambda_handler(event, context):
    """
    Handle DICOM file upload and initiate processing pipeline
    """
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        
        # Extract metadata
        patient_id = body.get('patient_id')
        study_description = body.get('study_description', 'Brain CT - Stroke Protocol')
        file_key = body.get('file_key')  # S3 key of uploaded DICOM
        
        # Validate required fields
        if not patient_id or not file_key:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'patient_id and file_key are required'})
            }
        
        # Generate unique study ID
        study_id = f"STUDY-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.utcnow().isoformat()
        
        # Verify DICOM file exists in S3
        try:
            s3_client.head_object(Bucket=UPLOAD_BUCKET, Key=file_key)
        except:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'DICOM file not found in S3'})
            }
        
        # Start HealthImaging import job
        # HealthImaging expects a folder path, not a single file
        folder_path = '/'.join(file_key.split('/')[:-1]) + '/'
        import_response = start_healthimaging_import(
            study_id=study_id,
            s3_uri=f"s3://{UPLOAD_BUCKET}/{folder_path}"
        )
        
        # Store metadata in DynamoDB
        metadata = {
            'study_id': study_id,
            'patient_id': patient_id,
            'upload_timestamp': timestamp,
            'study_description': study_description,
            's3_bucket': UPLOAD_BUCKET,
            's3_key': file_key,
            'datastore_id': DATASTORE_ID,
            'import_job_id': import_response['jobId'],
            'status': 'IMPORTING',
            'processing_stage': 'ingestion'
        }
        
        save_to_dynamodb(metadata)
        
        # Trigger Step Functions workflow (will wait for import completion)
        trigger_workflow(study_id, metadata)
        
        return {
            'statusCode': 202,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'DICOM ingestion started',
                'study_id': study_id,
                'import_job_id': import_response['jobId'],
                'status': 'processing'
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def start_healthimaging_import(study_id, s3_uri):
    """
    Start AWS HealthImaging import job
    """
    response = healthimaging_client.start_dicom_import_job(
        datastoreId=DATASTORE_ID,
        dataAccessRoleArn=os.environ['HEALTHIMAGING_ROLE_ARN'],
        inputS3Uri=s3_uri,
        outputS3Uri=f"s3://{UPLOAD_BUCKET}/healthimaging-output/{study_id}/"
    )
    
    return {
        'jobId': response['jobId'],
        'datastoreId': response['datastoreId']
    }


def save_to_dynamodb(metadata):
    """
    Save study metadata to DynamoDB
    """
    table = dynamodb.Table(METADATA_TABLE)
    table.put_item(Item=metadata)


def trigger_workflow(study_id, metadata):
    """
    Trigger Step Functions workflow for processing
    """
    sfn_client.start_execution(
        stateMachineArn=STEP_FUNCTION_ARN,
        name=f"stroke-analysis-{study_id}",
        input=json.dumps(metadata)
    )


# For local testing
if __name__ == "__main__":
    test_event = {
        'body': json.dumps({
            'patient_id': 'P123456',
            'study_description': 'Brain CT - Suspected Stroke',
            'file_key': 'uploads/sample_brain_ct.dcm'
        })
    }
    
    print(lambda_handler(test_event, None))
