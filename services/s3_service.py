"""
S3 service for object storage operations.
"""
import json
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
from logger_config import get_logger

logger = get_logger(__name__)


class S3Service:
    """Service for S3 operations."""
    
    def __init__(self, bucket_name: str):
        """
        Initialize S3 service.
        
        Args:
            bucket_name: Name of the S3 bucket
        """
        self.bucket_name = bucket_name
        self._s3_resource = None
        self._s3_client = None
    
    @property
    def s3_resource(self):
        """Lazy initialization of S3 resource."""
        if self._s3_resource is None:
            self._s3_resource = boto3.resource('s3')
        return self._s3_resource
    
    @property
    def s3_client(self):
        """Lazy initialization of S3 client."""
        if self._s3_client is None:
            self._s3_client = boto3.client('s3')
        return self._s3_client
    
    def object_exists(self, key: str) -> bool:
        """
        Check if an object exists in the bucket.
        
        Args:
            key: S3 object key
            
        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                return False
            # For other errors, log and return False (fail-open)
            logger.warning(f'S3 head_object failed for key {key}: {str(e)}')
            return False
    
    def put_object(
        self,
        key: str,
        body: bytes | str,
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Put an object into S3 bucket.
        
        Args:
            key: S3 object key
            body: Object body (bytes or string)
            metadata: Optional metadata dictionary
            
        Raises:
            ClientError: If S3 operation fails
        """
        s3_object = self.s3_resource.Object(self.bucket_name, key)
        
        put_kwargs = {}
        if isinstance(body, str):
            put_kwargs['Body'] = body.encode('UTF-8')
        else:
            put_kwargs['Body'] = body
        
        if metadata:
            put_kwargs['Metadata'] = metadata
        
        s3_object.put(**put_kwargs)
        logger.info(f'Successfully put object to s3://{self.bucket_name}/{key}')
    
    def put_json_object(
        self,
        key: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Put a JSON object into S3 bucket.
        
        Args:
            key: S3 object key
            data: Dictionary to serialize as JSON
            metadata: Optional metadata dictionary
            
        Raises:
            ClientError: If S3 operation fails
        """
        json_body = json.dumps(data)
        self.put_object(key, json_body, metadata)
    
    def put_json_lines(
        self,
        key: str,
        records: list[Dict[str, Any]]
    ) -> None:
        """
        Put records as JSON Lines format (one JSON object per line).
        
        Args:
            key: S3 object key
            records: List of dictionaries to write as JSON Lines
            
        Raises:
            ClientError: If S3 operation fails
        """
        json_lines = '\n'.join(json.dumps(record) for record in records)
        self.put_object(key, json_lines)
        logger.info(f'Successfully put {len(records)} records as JSON Lines to s3://{self.bucket_name}/{key}')

