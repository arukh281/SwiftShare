from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException
from typing import Optional, Dict, Any

class S3Manager:
    def __init__(self, skip_verification: bool = False):
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = os.getenv("AWS_REGION")
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        
        if not all([self.aws_access_key_id, self.aws_secret_access_key, self.region, self.bucket_name]):
            raise ValueError("Missing required AWS credentials in environment variables")
        
        try:
            self.client = boto3.client(
                "s3",
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region,
            )
            # Verify bucket exists and is accessible (skip in test mode)
            if not skip_verification:
                self.client.head_bucket(Bucket=self.bucket_name)
        except NoCredentialsError:
            raise HTTPException(status_code=500, detail="AWS credentials not found or invalid")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise HTTPException(status_code=500, detail=f"S3 bucket '{self.bucket_name}' not found")
            elif error_code == '403':
                raise HTTPException(status_code=500, detail=f"Access denied to S3 bucket '{self.bucket_name}'")
            else:
                raise HTTPException(status_code=500, detail=f"Error accessing S3: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error initializing S3 client: {str(e)}")

    def upload_file(self, file_data: bytes, key: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Upload a file to S3 with optional metadata."""
        try:
            extra_args = {'Metadata': metadata} if metadata else {}
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_data,
                **extra_args
            )
        except ClientError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error uploading file to S3: {str(e)}"
            )

    def download_file(self, key: str) -> bytes:
        """Download a file from S3."""
        try:
            print(f"Attempting to download file with key: {key}")
            print(f"Using bucket: {self.bucket_name}")
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            print("Successfully retrieved object from S3")
            return response['Body'].read()
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"S3 Error - Code: {error_code}, Message: {error_message}")
            if error_code == 'NoSuchKey':
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found in S3: {key}"
                )
            raise HTTPException(
                status_code=500,
                detail=f"Error downloading file from S3: {str(e)}"
            )
        except Exception as e:
            print(f"Unexpected error during download: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error downloading file from S3: {str(e)}"
            )

    def delete_file(self, key: str) -> None:
        """Delete a file from S3."""
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
        except ClientError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error deleting file from S3: {str(e)}"
            )

    def get_file_metadata(self, key: str) -> Dict[str, Any]:
        """Get metadata for a file in S3."""
        try:
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return response.get('Metadata', {})
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found in S3: {key}"
                )
            raise HTTPException(
                status_code=500,
                detail=f"Error getting file metadata from S3: {str(e)}"
            )

# Create a singleton instance
is_test_mode = os.getenv("TESTING", "").lower() == "true"
s3_manager = S3Manager(skip_verification=is_test_mode) 