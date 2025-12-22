"""
Custom exception classes for Lambda handlers and services.
"""
from typing import Optional, Dict, Any


class InvictusAPIError(Exception):
    """Exception raised for Invictus API errors."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Invictus API error.
        
        Args:
            message: Error message
            status_code: HTTP status code if available
            response_data: Response data if available
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data


class S3OperationError(Exception):
    """Exception raised for S3 operation errors."""
    
    def __init__(
        self,
        message: str,
        bucket: Optional[str] = None,
        key: Optional[str] = None,
        operation: Optional[str] = None
    ):
        """
        Initialize S3 operation error.
        
        Args:
            message: Error message
            bucket: S3 bucket name if available
            key: S3 object key if available
            operation: Operation name if available
        """
        super().__init__(message)
        self.message = message
        self.bucket = bucket
        self.key = key
        self.operation = operation


class ValidationError(Exception):
    """Exception raised for validation errors."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None
    ):
        """
        Initialize validation error.
        
        Args:
            message: Error message
            field: Field name that failed validation if available
            value: Invalid value if available
        """
        super().__init__(message)
        self.message = message
        self.field = field
        self.value = value


class IdempotencyError(Exception):
    """Exception raised for idempotency operation errors."""
    
    def __init__(
        self,
        message: str,
        idempotency_key: Optional[str] = None,
        operation: Optional[str] = None
    ):
        """
        Initialize idempotency error.
        
        Args:
            message: Error message
            idempotency_key: Idempotency key if available
            operation: Operation name if available
        """
        super().__init__(message)
        self.message = message
        self.idempotency_key = idempotency_key
        self.operation = operation

