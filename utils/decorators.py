"""
Handler decorators for error handling, logging, and response formatting.
"""
import functools
import uuid
import traceback
from typing import Callable, Any, Dict
from logger_config import get_logger

logger = get_logger(__name__)


def lambda_handler(
    func: Callable[[Any, Any], Any]
) -> Callable[[Any, Any], Dict[str, Any]]:
    """
    Decorator for Lambda handler functions.
    
    Provides:
    - Error handling with structured error responses
    - Request correlation IDs for logging
    - Response formatting
    - Logging context
    
    Args:
        func: The handler function to decorate
        
    Returns:
        Decorated handler function
    """
    @functools.wraps(func)
    def wrapper(event: Any, context: Any) -> Dict[str, Any]:
        # Generate correlation ID for request tracking
        correlation_id = str(uuid.uuid4())
        
        # Log handler invocation
        logger.info(
            f"Handler {func.__name__} invoked",
            extra={
                "correlation_id": correlation_id,
                "handler": func.__name__,
                "request_id": getattr(context, "aws_request_id", None) if context else None
            }
        )
        
        try:
            # Call the actual handler
            result = func(event, context)
            
            # Ensure result is a dictionary
            if not isinstance(result, dict):
                logger.warning(
                    f"Handler {func.__name__} returned non-dict result, converting",
                    extra={"correlation_id": correlation_id}
                )
                # For Step Functions compatibility, wrap in dict if needed
                if isinstance(result, (list, str)):
                    result = {"result": result}
                else:
                    result = {"data": result}
            
            # Add correlation ID to response metadata
            if "metadata" not in result:
                result["metadata"] = {}
            result["metadata"]["correlation_id"] = correlation_id
            
            logger.info(
                f"Handler {func.__name__} completed successfully",
                extra={"correlation_id": correlation_id}
            )
            
            return result
            
        except ValueError as e:
            # Validation errors - return 400-like response
            error_response = {
                "error": {
                    "type": "ValidationError",
                    "message": str(e),
                    "correlation_id": correlation_id
                },
                "metadata": {
                    "correlation_id": correlation_id,
                    "handler": func.__name__
                }
            }
            
            logger.warning(
                f"Handler {func.__name__} validation error: {str(e)}",
                extra={"correlation_id": correlation_id}
            )
            
            return error_response
            
        except Exception as e:
            # Unexpected errors - return 500-like response
            error_traceback = traceback.format_exc()
            
            error_response = {
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "correlation_id": correlation_id
                },
                "metadata": {
                    "correlation_id": correlation_id,
                    "handler": func.__name__
                }
            }
            
            logger.error(
                f"Handler {func.__name__} failed: {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "traceback": error_traceback
                },
                exc_info=True
            )
            
            return error_response
    
    return wrapper

