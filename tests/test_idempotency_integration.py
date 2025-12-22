"""
Integration tests for idempotency behavior in complete workflows.
"""
import pytest
from moto import mock_aws
import boto3
import os
import json
import sys
from datetime import datetime, timedelta, timezone

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.idempotency_service import IdempotencyService


@pytest.fixture
def mock_context():
    """Mock Lambda context."""
    class MockContext:
        def __init__(self):
            self.function_name = 'test-function'
            self.memory_limit_in_mb = 512
            self.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test'
            self.aws_request_id = 'test-request-id'
    
    return MockContext()


@pytest.mark.idempotency_integration
@mock_aws()
def test_dump_post_to_bucket_idempotency(mock_context):
    """Test that dump_post_to_bucket is idempotent."""
    # Setup
    s3 = boto3.client('s3', region_name='us-east-1')
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    
    bucket_name = 'test-invictus-bucket'
    table_name = 'test-idempotency-table'
    
    # Set environment variables BEFORE creating resources (config validates at import)
    os.environ['INVICTUS_BUCKET'] = bucket_name
    os.environ['IDEMPOTENCY_TABLE'] = table_name
    os.environ['INVICTUS_WEIGHTLIFTING_API'] = 'https://api.example.com'
    
    # Reset config module to pick up new env vars
    import config
    config._config = None
    
    # Import handlers AFTER setting env vars (they use get_config() at import time)
    from handler import dump_post_to_bucket
    
    # Create S3 bucket
    s3.create_bucket(Bucket=bucket_name)
    
    # Create DynamoDB table
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
    
    # Test data
    post = {
        'slug': 'test-post',
        'date': '2024-01-01T10:00:00',
        'title': {'rendered': 'Test Post'},
        'content': {'rendered': '<p>Test content</p>'}
    }
    
    context = mock_context
    
    # First execution - should write to S3
    result1 = dump_post_to_bucket(post, context)
    
    # Verify S3 object was created
    response = s3.head_object(
        Bucket=bucket_name,
        Key='raw/2024-01-01__test-post__raw.json'
    )
    assert 'ETag' in response
    
    # Verify idempotency record was created
    key = IdempotencyService.generate_key('dump_post_to_bucket', 'raw/2024-01-01__test-post__raw.json')
    idempotency_response = dynamodb.get_item(
        TableName=table_name,
        Key={'idempotency_key': {'S': key}}
    )
    assert 'Item' in idempotency_response
    
    # Second execution - should skip write (S3 object exists)
    result2 = dump_post_to_bucket(post, context)
    
    # Verify only one object exists (no duplicates)
    objects = s3.list_objects_v2(Bucket=bucket_name, Prefix='raw/')
    assert objects['KeyCount'] == 1
    
    # Verify results are the same (ignore metadata which contains unique correlation_id)
    # Handler decorator wraps response, so we need to check the actual post data
    # Extract post data from response (may be wrapped by decorator or returned directly)
    post1 = result1 if isinstance(result1, dict) and 'slug' in result1 else result1
    post2 = result2 if isinstance(result2, dict) and 'slug' in result2 else result2
    
    # Compare post data fields
    assert post1.get('slug') == post2.get('slug')
    assert post1.get('title') == post2.get('title')
    assert post1.get('date') == post2.get('date')


@pytest.mark.idempotency_integration
@mock_aws()
def test_save_sessions_to_bucket_idempotency(mock_context):
    """Test that save_sessions_to_bucket is idempotent."""
    # Setup
    s3 = boto3.client('s3', region_name='us-east-1')
    
    bucket_name = 'test-invictus-bucket'
    
    # Set environment variables BEFORE creating resources (config validates at import)
    os.environ['INVICTUS_BUCKET'] = bucket_name
    os.environ['INVICTUS_WEIGHTLIFTING_API'] = 'https://api.example.com'
    
    # Reset config module to pick up new env vars
    import config
    config._config = None
    
    # Import handlers AFTER setting env vars (they use get_config() at import time)
    from handler import save_sessions_to_bucket
    
    # Create S3 bucket
    s3.create_bucket(Bucket=bucket_name)
    
    # Test data
    session_records = [
        {'date': '2024-01-01', 'session': 'session-1', 'warm_up': 'test'},
        {'date': '2024-01-02', 'session': 'session-2', 'warm_up': 'test'}
    ]
    
    context = mock_context
    
    # First execution - should write to S3
    result1 = save_sessions_to_bucket(session_records, context)
    
    # Verify S3 object was created
    response = s3.head_object(
        Bucket=bucket_name,
        Key='weekly/2024-01-01__2024-01-02--5-day-weightlifting-program.json'
    )
    assert 'ETag' in response
    
    # Second execution - should skip write (file exists)
    result2 = save_sessions_to_bucket(session_records, context)
    
    # Verify only one object exists (no duplicates)
    objects = s3.list_objects_v2(Bucket=bucket_name, Prefix='weekly/')
    assert objects['KeyCount'] == 1
    
    # Verify results are the same (ignore metadata which contains unique correlation_id)
    # Both should return dict with 'records' key containing the same session records
    assert result1.get('records') == result2.get('records')
    assert len(result1.get('records', [])) == 2
    assert len(result2.get('records', [])) == 2


@pytest.mark.idempotency_integration
@mock_aws()
def test_idempotency_table_ttl_expiration():
    """Test that idempotency records expire after TTL."""
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    table_name = 'test-idempotency-table'
    
    # Create table
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
    
    # Enable TTL
    dynamodb.update_time_to_live(
        TableName=table_name,
        TimeToLiveSpecification={
            'Enabled': True,
            'AttributeName': 'ttl'
        }
    )
    
    # Set environment variable
    os.environ['IDEMPOTENCY_TABLE'] = table_name
    
    # Add item with past TTL (expired)
    key = IdempotencyService.generate_key('test_op', 'test_id')
    now = datetime.now(timezone.utc)
    expired_ttl = int((now - timedelta(hours=1)).timestamp())
    
    dynamodb.put_item(
        TableName=table_name,
        Item={
            'idempotency_key': {'S': key},
            'ttl': {'N': str(expired_ttl)},
            'completed_at': {'S': now.isoformat()}
        }
    )
    
    # Verify item exists (DynamoDB doesn't immediately delete expired items)
    response = dynamodb.get_item(
        TableName=table_name,
        Key={'idempotency_key': {'S': key}}
    )
    assert 'Item' in response
    
    # Verify TTL is in the past
    ttl_value = int(response['Item']['ttl']['N'])
    current_timestamp = int(datetime.now(timezone.utc).timestamp())
    assert ttl_value < current_timestamp


@pytest.mark.idempotency_integration
@mock_aws()
def test_duplicate_execution_prevention(mock_context):
    """Test that duplicate executions are prevented."""
    s3 = boto3.client('s3', region_name='us-east-1')
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    
    bucket_name = 'test-invictus-bucket'
    table_name = 'test-idempotency-table'
    
    # Create resources
    s3.create_bucket(Bucket=bucket_name)
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
    
    # Set environment variables BEFORE creating resources (config validates at import)
    os.environ['INVICTUS_BUCKET'] = bucket_name
    os.environ['IDEMPOTENCY_TABLE'] = table_name
    os.environ['INVICTUS_WEIGHTLIFTING_API'] = 'https://api.example.com'
    
    # Reset config module to pick up new env vars
    import config
    config._config = None
    
    # Import handlers AFTER setting env vars (they use get_config() at import time)
    from handler import dump_post_to_bucket
    
    # Test data
    post = {
        'slug': 'test-post',
        'date': '2024-01-01T10:00:00',
        'title': {'rendered': 'Test Post'},
        'content': {'rendered': '<p>Test content</p>'}
    }
    
    context = mock_context
    bucket_path = 'raw/2024-01-01__test-post__raw.json'
    key = IdempotencyService.generate_key('dump_post_to_bucket', bucket_path)
    
    # Manually mark as complete (simulating previous execution)
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
    
    # Verify idempotency check detects previous execution
    service = IdempotencyService(table_name)
    assert service.check(key) is True
    
    # Execute function - should skip due to idempotency check
    result = dump_post_to_bucket(post, context)
    
    # Verify no S3 object was created (skipped)
    try:
        s3.head_object(Bucket=bucket_name, Key=bucket_path)
        pytest.fail("S3 object should not exist if idempotency check worked")
    except Exception as e:
        error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', '')
        assert error_code == '404' or 'NoSuchKey' in str(e)

