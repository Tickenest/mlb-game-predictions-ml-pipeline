import json
import os
import boto3
from datetime import datetime

SAGEMAKER_CLIENT = boto3.client('sagemaker')
PIPELINE_NAME = os.environ.get('PIPELINE_NAME', 'mlb-predictions-training-pipeline')


def lambda_handler(event, context):
    """
    Triggered by S3 when new raw data is uploaded.
    Starts the SageMaker training pipeline.
    """
    print(f"S3 event received: {json.dumps(event)}")

    # Extract bucket and key from S3 event
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        print(f"New data uploaded: s3://{bucket}/{key}")

    # Start the SageMaker pipeline
    execution_name = f"mlb-pipeline-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    try:
        response = SAGEMAKER_CLIENT.start_pipeline_execution(
            PipelineName=PIPELINE_NAME,
            PipelineExecutionDisplayName=execution_name,
            PipelineExecutionDescription=f"Triggered by new data: {key}",
        )
        execution_arn = response['PipelineExecutionArn']
        print(f"Pipeline started: {execution_arn}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Pipeline started successfully',
                'execution_arn': execution_arn,
                'execution_name': execution_name,
            })
        }

    except Exception as e:
        print(f"Error starting pipeline: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }