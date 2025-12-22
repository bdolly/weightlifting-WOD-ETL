"""
Configuration module for environment variable validation and type-safe config.

This module validates all required environment variables at import time
and provides a type-safe configuration object.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Type-safe configuration object with validated environment variables."""
    
    invictus_bucket: str
    invictus_weightlifting_api: str
    invictus_weightlifting_api_cat_id: str
    invictus_user: Optional[str] = None
    invictus_pass: Optional[str] = None
    invictus_secret_name: Optional[str] = None
    idempotency_table: str = ""
    dynamodb_table: str = ""
    aws_region: str = "us-east-1"
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "Config":
        """
        Create Config instance from environment variables.
        
        Raises:
            ValueError: If required environment variables are missing or invalid.
        """
        invictus_bucket = os.environ.get("INVICTUS_BUCKET")
        if not invictus_bucket:
            raise ValueError(
                "INVICTUS_BUCKET environment variable is required"
            )
        
        invictus_weightlifting_api = os.environ.get("INVICTUS_WEIGHTLIFTING_API")
        if not invictus_weightlifting_api:
            raise ValueError(
                "INVICTUS_WEIGHTLIFTING_API environment variable is required"
            )
        
        invictus_weightlifting_api_cat_id = os.environ.get(
            "INVICTUS_WEIGHTLIFTING_API_CAT_ID", "213"
        )
        
        invictus_user = os.environ.get("INVICTUS_USER")
        invictus_pass = os.environ.get("INVICTUS_PASS")
        invictus_secret_name = os.environ.get("INVICTUS_SECRET_NAME")
        
        idempotency_table = os.environ.get("IDEMPOTENCY_TABLE", "")
        dynamodb_table = os.environ.get("DYNAMODB_TABLE", "")
        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        
        # Validate log level
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if log_level not in valid_log_levels:
            raise ValueError(
                f"LOG_LEVEL must be one of {valid_log_levels}, got: {log_level}"
            )
        
        return cls(
            invictus_bucket=invictus_bucket,
            invictus_weightlifting_api=invictus_weightlifting_api,
            invictus_weightlifting_api_cat_id=invictus_weightlifting_api_cat_id,
            invictus_user=invictus_user,
            invictus_pass=invictus_pass,
            invictus_secret_name=invictus_secret_name,
            idempotency_table=idempotency_table,
            dynamodb_table=dynamodb_table,
            aws_region=aws_region,
            log_level=log_level,
        )


# Global config instance - initialized at module import
# This will raise ValueError if required env vars are missing
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    
    Returns:
        Config: The validated configuration object
        
    Raises:
        ValueError: If required environment variables are missing or invalid.
    """
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config

