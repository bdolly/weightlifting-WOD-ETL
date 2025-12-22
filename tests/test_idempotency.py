"""
Tests for idempotency functions and behavior.
"""
import pytest
from moto import mock_aws
import boto3
import os
from datetime import datetime, timedelta, timezone
import sys

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.idempotency_service import IdempotencyService


@pytest.mark.idempotency
def test_generate_idempotency_key():
    """Test that idempotency key generation is deterministic."""
    operation = 'dump_post_to_bucket'
    identifier = 'raw/2024-01-01__test-post__raw.json'
    
    key1 = IdempotencyService.generate_key(operation, identifier)
    key2 = IdempotencyService.generate_key(operation, identifier)
    
    # Same inputs should produce same key
    assert key1 == key2
    assert len(key1) == 64  # SHA256 produces 64 hex characters
    
    # Different inputs should produce different keys
    key3 = IdempotencyService.generate_key(operation, 'different-identifier')
    assert key1 != key3
    
    key4 = IdempotencyService.generate_key('different_operation', identifier)
    assert key1 != key4


@pytest.mark.idempotency
@mock_aws()
def test_check_idempotency_not_found():
    """Test that check_idempotency returns False when key doesn't exist."""
    # Create table
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    table_name = 'test-idempotency-table'
    
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
    
    # Set environment variable
    os.environ['IDEMPOTENCY_TABLE'] = table_name
    
    # Check non-existent key
    service = IdempotencyService(table_name)
    key = IdempotencyService.generate_key('test_op', 'test_id')
    result = service.check(key)
    
    assert result is False


@pytest.mark.idempotency
@mock_aws()
def test_check_idempotency_found():
    """Test that check_idempotency returns True when key exists."""
    # Create table
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    table_name = 'test-idempotency-table'
    
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
    
    # Set environment variable
    os.environ['IDEMPOTENCY_TABLE'] = table_name
    
    # Add item to table
    service = IdempotencyService(table_name)
    key = IdempotencyService.generate_key('test_op', 'test_id')
    now = datetime.now(timezone.utc)
    ttl_timestamp = int((now + timedelta(hours=24)).timestamp())
    
    dynamodb.put_item(
        TableName=table_name,
        Item={
            'idempotency_key': {'S': key},
            'ttl': {'N': str(ttl_timestamp)},
            'completed_at': {'S': now.isoformat()}
        }
    )
    
    # Check existing key
    result = service.check(key)
    
    assert result is True


@pytest.mark.idempotency
def test_check_idempotency_fail_open_no_table():
    """Test that check_idempotency fails open when table not configured."""
    # Remove environment variable
    if 'IDEMPOTENCY_TABLE' in os.environ:
        del os.environ['IDEMPOTENCY_TABLE']
    
    service = IdempotencyService(None)
    key = IdempotencyService.generate_key('test_op', 'test_id')
    result = service.check(key)
    
    # Should return False (allow operation) when table not configured
    assert result is False


@pytest.mark.idempotency
@mock_aws()
def test_mark_idempotency_complete():
    """Test that mark_idempotency_complete writes to DynamoDB."""
    # Create table
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    table_name = 'test-idempotency-table'
    
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
    
    # Set environment variable
    os.environ['IDEMPOTENCY_TABLE'] = table_name
    
    # Mark as complete
    service = IdempotencyService(table_name)
    key = IdempotencyService.generate_key('test_op', 'test_id')
    service.mark_complete(key, ttl_hours=24)
    
    # Verify item was written
    response = dynamodb.get_item(
        TableName=table_name,
        Key={'idempotency_key': {'S': key}}
    )
    
    assert 'Item' in response
    assert 'ttl' in response['Item']
    assert 'completed_at' in response['Item']


@pytest.mark.idempotency
def test_mark_idempotency_complete_fail_open_no_table():
    """Test that mark_idempotency_complete fails open when table not configured."""
    # Remove environment variable
    if 'IDEMPOTENCY_TABLE' in os.environ:
        del os.environ['IDEMPOTENCY_TABLE']
    
    service = IdempotencyService(None)
    key = IdempotencyService.generate_key('test_op', 'test_id')
    
    # Should not raise exception
    service.mark_complete(key)


@pytest.mark.idempotency
@mock_aws()
def test_s3_idempotency_check():
    """Test S3 idempotency check using head_object."""
    from services.s3_service import S3Service
    
    # Create bucket and object
    s3 = boto3.client('s3', region_name='us-east-1')
    bucket_name = 'test-bucket'
    key = 'raw/2024-01-01__test-post__raw.json'
    
    s3.create_bucket(Bucket=bucket_name)
    s3.put_object(Bucket=bucket_name, Key=key, Body=b'test content')
    
    # Use S3Service to check object existence
    s3_service = S3Service(bucket_name)
    assert s3_service.object_exists(key) is True
    assert s3_service.object_exists('non-existent-key') is False


@pytest.mark.idempotency
@mock_aws()
def test_dynamodb_conditional_write():
    """Test DynamoDB conditional write prevents duplicates."""
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    table_name = 'test-sessions-table'
    
    # Create table
    dynamodb.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {'AttributeName': 'date', 'AttributeType': 'S'},
            {'AttributeName': 'session', 'AttributeType': 'S'}
        ],
        KeySchema=[
            {'AttributeName': 'date', 'KeyType': 'HASH'},
            {'AttributeName': 'session', 'KeyType': 'RANGE'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # First write should succeed
    # Use ExpressionAttributeNames to escape reserved keyword 'date'
    dynamodb.put_item(
        TableName=table_name,
        Item={
            'date': {'S': '2024-01-01'},
            'session': {'S': 'session-1'},
            'warm_up': {'S': 'test'}
        },
        ConditionExpression='attribute_not_exists(#date) AND attribute_not_exists(#session)',
        ExpressionAttributeNames={
            '#date': 'date',
            '#session': 'session'
        }
    )
    
    # Verify item exists
    response = dynamodb.get_item(
        TableName=table_name,
        Key={'date': {'S': '2024-01-01'}, 'session': {'S': 'session-1'}}
    )
    assert 'Item' in response
    
    # Second write with same key should fail with ConditionalCheckFailedException
    with pytest.raises(Exception) as exc_info:
        dynamodb.put_item(
            TableName=table_name,
            Item={
                'date': {'S': '2024-01-01'},
                'session': {'S': 'session-1'},
                'warm_up': {'S': 'different'}
            },
            ConditionExpression='attribute_not_exists(#date) AND attribute_not_exists(#session)',
            ExpressionAttributeNames={
                '#date': 'date',
                '#session': 'session'
            }
        )
    
    assert 'ConditionalCheckFailedException' in str(exc_info.value)

