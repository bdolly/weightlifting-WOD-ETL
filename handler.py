import os
import json
import requests
import boto3
import hashlib
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from transforms import *
from dateutil.parser import parse


s3_resource = boto3.resource('s3')
s3_client = boto3.client('s3')
dynamodb_client = boto3.client('dynamodb')
invictus_api = os.environ['INVICTUS_WEIGHTLIFTING_API']


def generate_idempotency_key(operation, identifier):
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


def check_idempotency(idempotency_key):
    """
    Check if an operation has already been completed.
    
    Args:
        idempotency_key: The idempotency key to check
    
    Returns:
        True if operation already completed, False otherwise
    
    Note:
        Fail-open: Returns False (allow operation) if check fails
    """
    try:
        table_name = os.environ.get('IDEMPOTENCY_TABLE')
        if not table_name:
            print('WARNING: IDEMPOTENCY_TABLE not set, skipping idempotency check')
            return False
        
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={'idempotency_key': {'S': idempotency_key}}
        )
        
        if 'Item' in response:
            print(f'Idempotency check: Operation already completed (key: {idempotency_key[:16]}...)')
            return True
        
        return False
    except Exception as e:
        # Fail-open: if idempotency check fails, allow the operation
        print(f'WARNING: Idempotency check failed: {str(e)}, allowing operation to proceed')
        return False


def mark_idempotency_complete(idempotency_key, ttl_hours=24):
    """
    Mark an operation as complete in the idempotency table.
    
    Args:
        idempotency_key: The idempotency key to mark as complete
        ttl_hours: Number of hours until the record expires (default: 24)
    
    Note:
        Fail-open: Logs error but doesn't raise exception
    """
    try:
        table_name = os.environ.get('IDEMPOTENCY_TABLE')
        if not table_name:
            print('WARNING: IDEMPOTENCY_TABLE not set, skipping idempotency marking')
            return
        
        # Calculate TTL timestamp (Unix epoch time)
        ttl_timestamp = int((datetime.utcnow() + timedelta(hours=ttl_hours)).timestamp())
        
        dynamodb_client.put_item(
            TableName=table_name,
            Item={
                'idempotency_key': {'S': idempotency_key},
                'ttl': {'N': str(ttl_timestamp)},
                'completed_at': {'S': datetime.utcnow().isoformat()}
            }
        )
        print(f'Idempotency marked complete (key: {idempotency_key[:16]}..., TTL: {ttl_hours}h)')
    except Exception as e:
        # Fail-open: if marking fails, log but don't fail the operation
        print(f'WARNING: Failed to mark idempotency complete: {str(e)}')


def GET_invictus_post(event, context):
    """GET Invicitus Weightlifting WP blog post"""
    posts_per_page = event.get('posts_per_page', False) or 1
    page_num = event.get('page', False) or 1
    url = invictus_api+"&per_page="+str(posts_per_page)+"&page="+str(page_num)
    
    # Add browser-like headers to bypass Mod_Security
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/html, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    api_req = requests.get(url, headers=headers)
    # check if the request is successful
    if api_req.status_code != 200:
        raise Exception(f"Failed to get invictus post: {api_req.status_code} {api_req.text}")

    return api_req.json()
    

def dump_post_to_bucket(invictus_raw_post, context):

    post = invictus_raw_post
    post_date_time_obj = parse(post["date"])

    bucket_path = 'raw/{posted}__{slug}__raw.json'.format(
        slug=post["slug"], posted=post_date_time_obj.date())

    bucket_name = os.environ['INVICTUS_BUCKET']
    
    # S3 idempotency check: skip write if object already exists
    try:
        s3_client.head_object(Bucket=bucket_name, Key=bucket_path)
        print(f'- Post "{post["title"]["rendered"]}" already exists in bucket, skipping write')
        return post
    except Exception as e:
        error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', '')
        if error_code == '404':
            # Object doesn't exist, proceed with write
            pass
        else:
            # Fail-open: if check fails, allow the write
            print(f'WARNING: S3 idempotency check failed: {str(e)}, proceeding with write')

    # Generate idempotency key for metadata
    idempotency_key = generate_idempotency_key('dump_post_to_bucket', bucket_path)

    s3object = s3_resource.Object(bucket_name, bucket_path)
    print('- Dumping post "{}" to bucket'.format(post["title"]["rendered"]))

    s3object.put(
        Body=(bytes(json.dumps(post).encode('UTF-8'))),
        Metadata={
            'idempotency_key': idempotency_key,
            'operation': 'dump_post_to_bucket'
        }
    )

    return post


def strip_post_html(post, ctx):
    """
        strip HTML from post conent because it's not well structured markup.
    """

    post_text_raw = BeautifulSoup(
        post['content']['rendered'], 'html.parser')

    return post_text_raw.get_text()


def save_sessions_to_bucket(session_records, context):
    """Save session records to S3 bucket using standard library"""
    # Parse dates and find min/max
    dates = []
    for record in session_records:
        if 'date' in record:
            date_obj = parse(record['date'])
            dates.append(date_obj)
            # Ensure date is formatted as YYYY-MM-DD
            record['date'] = date_obj.strftime('%Y-%m-%d')
    
    if not dates:
        raise ValueError("No dates found in session records")
    
    start_date = min(dates).date()
    end_date = max(dates).date()
    
    bucket_path = 'weekly/{start_date}__{end_date}--5-day-weightlifting-program.json'.format(
        start_date=start_date, end_date=end_date)

    s3object = s3_resource.Object(os.environ['INVICTUS_BUCKET'], bucket_path)

    # Save to bucket as lines of json so that we can query it using S3 select
    # JSON Lines format: one JSON object per line
    json_lines = '\n'.join(json.dumps(record) for record in session_records)
    
    s3object.put(
        Body=json_lines
    )

    return json.dumps(session_records)
