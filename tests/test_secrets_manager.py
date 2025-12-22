"""
Tests for Secrets Manager integration functions.
"""
import pytest
from moto import mock_aws
import boto3
import os
import json
import sys

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from handler import get_wordpress_credentials


@pytest.mark.secrets_manager
@mock_aws()
def test_get_wordpress_credentials_from_secrets_manager():
    """Test retrieving credentials from Secrets Manager."""
    # Set up environment
    os.environ['INVICTUS_SECRET_NAME'] = 'test-wordpress-credentials'
    os.environ['AWS_REGION'] = 'us-east-1'
    
    # Create Secrets Manager client and secret
    secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
    secret_name = 'test-wordpress-credentials'
    secret_value = {
        'username': 'test_user',
        'password': 'test_password'
    }
    
    secrets_client.create_secret(
        Name=secret_name,
        SecretString=json.dumps(secret_value)
    )
    
    # Test credential retrieval
    username, password = get_wordpress_credentials()
    
    assert username == 'test_user'
    assert password == 'test_password'
    
    # Cleanup
    del os.environ['INVICTUS_SECRET_NAME']
    del os.environ['AWS_REGION']


@pytest.mark.secrets_manager
@mock_aws()
def test_get_wordpress_credentials_fallback_to_env_vars():
    """Test fallback to environment variables when Secrets Manager fails."""
    # Set up environment variables (no secret name)
    os.environ['INVICTUS_USER'] = 'env_user'
    os.environ['INVICTUS_PASS'] = 'env_pass'
    os.environ['AWS_REGION'] = 'us-east-1'
    
    # Don't create secret - should fallback to env vars
    username, password = get_wordpress_credentials()
    
    assert username == 'env_user'
    assert password == 'env_pass'
    
    # Cleanup
    del os.environ['INVICTUS_USER']
    del os.environ['INVICTUS_PASS']
    del os.environ['AWS_REGION']


@pytest.mark.secrets_manager
@mock_aws()
def test_get_wordpress_credentials_secrets_manager_missing_fields():
    """Test fallback when Secrets Manager secret exists but missing fields."""
    # Set up environment
    os.environ['INVICTUS_SECRET_NAME'] = 'test-wordpress-credentials'
    os.environ['INVICTUS_USER'] = 'env_user'
    os.environ['INVICTUS_PASS'] = 'env_pass'
    os.environ['AWS_REGION'] = 'us-east-1'
    
    # Create secret with missing fields
    secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
    secret_name = 'test-wordpress-credentials'
    secret_value = {}  # Empty secret
    
    secrets_client.create_secret(
        Name=secret_name,
        SecretString=json.dumps(secret_value)
    )
    
    # Should fallback to env vars
    username, password = get_wordpress_credentials()
    
    assert username == 'env_user'
    assert password == 'env_pass'
    
    # Cleanup
    del os.environ['INVICTUS_SECRET_NAME']
    del os.environ['INVICTUS_USER']
    del os.environ['INVICTUS_PASS']
    del os.environ['AWS_REGION']


@pytest.mark.secrets_manager
@mock_aws()
def test_get_wordpress_credentials_secrets_manager_error():
    """Test fallback when Secrets Manager throws an error."""
    # Set up environment
    os.environ['INVICTUS_SECRET_NAME'] = 'non-existent-secret'
    os.environ['INVICTUS_USER'] = 'env_user'
    os.environ['INVICTUS_PASS'] = 'env_pass'
    os.environ['AWS_REGION'] = 'us-east-1'
    
    # Don't create secret - should fallback to env vars
    username, password = get_wordpress_credentials()
    
    assert username == 'env_user'
    assert password == 'env_pass'
    
    # Cleanup
    del os.environ['INVICTUS_SECRET_NAME']
    del os.environ['INVICTUS_USER']
    del os.environ['INVICTUS_PASS']
    del os.environ['AWS_REGION']


@pytest.mark.secrets_manager
def test_get_wordpress_credentials_both_unavailable():
    """Test error when both Secrets Manager and env vars are unavailable."""
    # Clear all credential-related environment variables
    for key in ['INVICTUS_SECRET_NAME', 'INVICTUS_USER', 'INVICTUS_PASS']:
        if key in os.environ:
            del os.environ[key]
    
    # Should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        get_wordpress_credentials()
    
    assert 'WordPress credentials not found' in str(exc_info.value)


@pytest.mark.secrets_manager
@mock_aws()
def test_get_wordpress_credentials_priority_secrets_manager_first():
    """Test that Secrets Manager takes priority over env vars when both exist."""
    # Set up both Secrets Manager and env vars
    os.environ['INVICTUS_SECRET_NAME'] = 'test-wordpress-credentials'
    os.environ['INVICTUS_USER'] = 'env_user'
    os.environ['INVICTUS_PASS'] = 'env_pass'
    os.environ['AWS_REGION'] = 'us-east-1'
    
    # Create Secrets Manager secret
    secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
    secret_name = 'test-wordpress-credentials'
    secret_value = {
        'username': 'secret_user',
        'password': 'secret_pass'
    }
    
    secrets_client.create_secret(
        Name=secret_name,
        SecretString=json.dumps(secret_value)
    )
    
    # Should use Secrets Manager (not env vars)
    username, password = get_wordpress_credentials()
    
    assert username == 'secret_user'
    assert password == 'secret_pass'
    
    # Cleanup
    del os.environ['INVICTUS_SECRET_NAME']
    del os.environ['INVICTUS_USER']
    del os.environ['INVICTUS_PASS']
    del os.environ['AWS_REGION']

