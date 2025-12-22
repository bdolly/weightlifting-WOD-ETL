"""
Idempotency service for tracking completed operations.
"""
import hashlib
import datetime as dt
from datetime import timedelta, timezone
from typing import Optional
from logger_config import get_logger
from .dynamodb_service import DynamoDBService

logger = get_logger(__name__)


class IdempotencyService:
    """Service for idempotency operations."""
    
    def __init__(self, table_name: Optional[str] = None):
        """
        Initialize idempotency service.
        
        Args:
            table_name: Name of the idempotency DynamoDB table
        """
        self.table_name = table_name
        self.dynamodb_service = DynamoDBService()
    
    @staticmethod
    def generate_key(operation: str, identifier: str) -> str:
        """
        Generate a unique idempotency key for an operation.
        
        Args:
            operation: The operation name (e.g., 'dump_post_to_bucket', 'save_sessions_to_bucket')
            identifier: A unique identifier for the operation (e.g., S3 path, post slug)
        
        Returns:
            A SHA256 hash string representing the idempotency key
        """
        key_string = f"{operation}:{identifier}"
        return hashlib.sha256(key_string.encode('utf-8')).hexdigest()
    
    def check(self, idempotency_key: str) -> bool:
        """
        Check if an operation has already been completed.
        
        Args:
            idempotency_key: The idempotency key to check
        
        Returns:
            True if operation already completed, False otherwise
        
        Note:
            Fail-open: Returns False (allow operation) if check fails
        """
        if not self.table_name:
            logger.warning('IDEMPOTENCY_TABLE not set, skipping idempotency check')
            return False
        
        try:
            item = self.dynamodb_service.get_item(
                table_name=self.table_name,
                key={'idempotency_key': {'S': idempotency_key}}
            )
            
            if item:
                logger.info(f'Idempotency check: Operation already completed (key: {idempotency_key[:16]}...)')
                return True
            
            return False
        except Exception as e:
            # Fail-open: if idempotency check fails, allow the operation
            logger.warning(f'Idempotency check failed: {str(e)}, allowing operation to proceed')
            return False
    
    def mark_complete(self, idempotency_key: str, ttl_hours: int = 24) -> None:
        """
        Mark an operation as complete in the idempotency table.
        
        Args:
            idempotency_key: The idempotency key to mark as complete
            ttl_hours: Number of hours until the record expires (default: 24)
        
        Note:
            Fail-open: Logs error but doesn't raise exception
        """
        if not self.table_name:
            logger.warning('IDEMPOTENCY_TABLE not set, skipping idempotency marking')
            return
        
        try:
            # Calculate TTL timestamp (Unix epoch time)
            now = dt.datetime.now(timezone.utc)
            ttl_timestamp = int((now + timedelta(hours=ttl_hours)).timestamp())
            
            self.dynamodb_service.put_item(
                table_name=self.table_name,
                item={
                    'idempotency_key': {'S': idempotency_key},
                    'ttl': {'N': str(ttl_timestamp)},
                    'completed_at': {'S': now.isoformat()}
                }
            )
            logger.info(f'Idempotency marked complete (key: {idempotency_key[:16]}..., TTL: {ttl_hours}h)')
        except Exception as e:
            # Fail-open: if marking fails, log but don't fail the operation
            logger.warning(f'Failed to mark idempotency complete: {str(e)}')

