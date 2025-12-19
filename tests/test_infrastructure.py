"""
Tests for infrastructure resources (Idempotency Table, Secrets Manager).
"""
import pytest
from moto import mock_dynamodb, mock_secretsmanager
import boto3
import json


@pytest.mark.infrastructure
@mock_dynamodb
def test_idempotency_table_creation():
    """Test that idempotency table can be created with correct schema."""
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    
    # Create table
    table_name = 'invictus-weightlifting-idempotency-dev'
    dynamodb.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {'AttributeName': 'idempotency_key', 'AttributeType': 'S'}
        ],
        KeySchema=[
            {'AttributeName': 'idempotency_key', 'KeyType': 'HASH'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # Verify table exists
    response = dynamodb.describe_table(TableName=table_name)
    assert response['Table']['TableName'] == table_name
    assert response['Table']['BillingModeSummary']['BillingMode'] == 'PAY_PER_REQUEST'
    assert len(response['Table']['KeySchema']) == 1
    assert response['Table']['KeySchema'][0]['AttributeName'] == 'idempotency_key'


@pytest.mark.infrastructure
@mock_secretsmanager
def test_secrets_manager_secret_creation():
    """Test that Secrets Manager secret can be created with correct structure."""
    secrets_manager = boto3.client('secretsmanager', region_name='us-east-1')
    
    # Create secret
    secret_name = 'invictus-weightlifting-wordpress-credentials-dev'
    secret_string = json.dumps({
        'username': 'test_user',
        'password': 'test_password'
    })
    
    secrets_manager.create_secret(
        Name=secret_name,
        Description='WordPress API credentials for Invictus blog',
        SecretString=secret_string
    )
    
    # Verify secret exists
    response = secrets_manager.describe_secret(SecretId=secret_name)
    assert response['Name'] == secret_name
    
    # Verify secret value
    secret_value = secrets_manager.get_secret_value(SecretId=secret_name)
    secret_data = json.loads(secret_value['SecretString'])
    assert secret_data['username'] == 'test_user'
    assert secret_data['password'] == 'test_password'


@pytest.mark.infrastructure
@mock_dynamodb
def test_idempotency_table_ttl():
    """Test that idempotency table has TTL enabled."""
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    
    table_name = 'invictus-weightlifting-idempotency-dev'
    dynamodb.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {'AttributeName': 'idempotency_key', 'AttributeType': 'S'}
        ],
        KeySchema=[
            {'AttributeName': 'idempotency_key', 'KeyType': 'HASH'}
        ],
        BillingMode='PAY_PER_REQUEST',
        TimeToLiveSpecification={
            'Enabled': True,
            'AttributeName': 'ttl'
        }
    )
    
    # Verify TTL is enabled
    response = dynamodb.describe_time_to_live(TableName=table_name)
    assert response['TimeToLiveSpecification']['Enabled'] is True
    assert response['TimeToLiveSpecification']['AttributeName'] == 'ttl'

