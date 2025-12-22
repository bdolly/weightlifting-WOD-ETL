"""
DynamoDB service for table operations.
"""
import boto3
from typing import Dict, Any, Optional, TYPE_CHECKING
from botocore.exceptions import ClientError
from logger_config import get_logger

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient
else:
    DynamoDBClient = Any

logger = get_logger(__name__)


class DynamoDBService:
    """Service for DynamoDB operations."""
    
    def __init__(self) -> None:
        """Initialize DynamoDB service."""
        self._client: Optional[DynamoDBClient] = None
    
    @property
    def client(self) -> DynamoDBClient:
        """Lazy initialization of DynamoDB client."""
        if self._client is None:
            self._client = boto3.client('dynamodb')
        return self._client
    
    def get_item(
        self,
        table_name: str,
        key: Dict[str, Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """
        Get an item from DynamoDB table.
        
        Args:
            table_name: Name of the DynamoDB table
            key: Dictionary with attribute names and values in DynamoDB format
            
        Returns:
            Item dictionary if found, None otherwise
            
        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            response = self.client.get_item(
                TableName=table_name,
                Key=key
            )
            return response.get('Item')
        except ClientError as e:
            logger.error(f'DynamoDB get_item failed for table {table_name}: {str(e)}')
            raise
    
    def put_item(
        self,
        table_name: str,
        item: Dict[str, Dict[str, str]]
    ) -> None:
        """
        Put an item into DynamoDB table.
        
        Args:
            table_name: Name of the DynamoDB table
            item: Item dictionary in DynamoDB format
            
        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            self.client.put_item(
                TableName=table_name,
                Item=item
            )
            logger.info(f'Successfully put item to DynamoDB table {table_name}')
        except ClientError as e:
            logger.error(f'DynamoDB put_item failed for table {table_name}: {str(e)}')
            raise

