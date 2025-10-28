"""
Lambda Function: HealthImaging Import Monitor
Triggered by: Step Functions (polling)
Purpose: Check if HealthImaging import job is complete
"""

import json
import boto3
import os

healthimaging_client = boto3.client('medical-imaging')
dynamodb = boto3.resource('dynamodb')

METADATA_TABLE = os.environ['DYNAMODB_TABLE']

def lambda_handler(event, context):
    """
    Check HealthImaging import job status
    Returns: job status for Step Functions decision
    """
    try:
        study_id = event['study_id']
        import_job_id = event['import_job_id']
        datastore_id = event['datastore_id']
        
        # Get import job status
        response = healthimaging_client.get_dicom_import_job(
            datastoreId=datastore_id,
            jobId=import_job_id
        )
        
        job_status = response['jobProperties']['jobStatus']
        
        # Update DynamoDB
        table = dynamodb.Table(METADATA_TABLE)
        table.update_item(
            Key={'study_id': study_id},
            UpdateExpression='SET import_status = :status',
            ExpressionAttributeValues={':status': job_status}
        )
        
        # Extract image set ID if completed
        image_set_id = None
        if job_status == 'COMPLETED':
            # Get the imported image set ID
            image_set_id = response['jobProperties'].get('outputS3Uri', '').split('/')[-2]
            
            # Update DynamoDB with image set ID
            table.update_item(
                Key={'study_id': study_id},
                UpdateExpression='SET image_set_id = :id, #st = :status',
                ExpressionAttributeNames={'#st': 'status'},
                ExpressionAttributeValues={
                    ':id': image_set_id,
                    ':status': 'READY_FOR_ANALYSIS'
                }
            )
        
        return {
            'study_id': study_id,
            'import_job_id': import_job_id,
            'datastore_id': datastore_id,
            'job_status': job_status,
            'image_set_id': image_set_id,
            'is_complete': job_status == 'COMPLETED',
            'has_error': job_status == 'FAILED'
        }
        
    except Exception as e:
        print(f"Error checking import status: {str(e)}")
        return {
            'job_status': 'ERROR',
            'error': str(e),
            'is_complete': False,
            'has_error': True
        }


if __name__ == "__main__":
    test_event = {
        'study_id': 'STUDY-abc123',
        'import_job_id': '12345678901234567890123456789012',
        'datastore_id': '1234567890abcdef1234567890abcdef'
    }
    
    print(lambda_handler(test_event, None))
