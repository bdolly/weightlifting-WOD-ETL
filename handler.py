"""
Lambda handler functions for Invictus Weightlifting WOD ETL pipeline.

This module provides Lambda handlers that use the service layer
for AWS operations and external API calls.
"""
import json
import os
import boto3
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from dateutil.parser import parse
from logger_config import get_logger
from config import get_config
from services.s3_service import S3Service
from services.idempotency_service import IdempotencyService
from services.invictus_api_service import InvictusAPIService
from utils.decorators import lambda_handler

logger = get_logger(__name__)


def get_wordpress_credentials() -> Tuple[Optional[str], Optional[str]]:
    """
    Retrieve WordPress credentials from Secrets Manager with fallback
    to environment variables.

    Returns:
        Tuple of (username, password) or (None, None) if unavailable.

    Raises:
        ValueError: If both Secrets Manager and env vars unavailable.
    """
    config = get_config()

    # Try Secrets Manager first if secret name is configured
    if config.invictus_secret_name:
        try:
            secrets_client = boto3.client(
                'secretsmanager', region_name=config.aws_region
            )
            response = secrets_client.get_secret_value(
                SecretId=config.invictus_secret_name
            )
            secret_string = response['SecretString']
            secret_data = json.loads(secret_string)

            username = secret_data.get('username')
            password = secret_data.get('password')

            if username and password:
                logger.info(
                    f'Successfully retrieved credentials from '
                    f'Secrets Manager: {config.invictus_secret_name}'
                )
                return username, password
            else:
                logger.warning(
                    f'Secrets Manager secret '
                    f'{config.invictus_secret_name} exists but missing '
                    f'username/password, falling back to env vars'
                )
        except Exception as e:
            logger.warning(
                f'Failed to retrieve credentials from Secrets Manager '
                f'({config.invictus_secret_name}): {str(e)}. '
                f'Falling back to environment variables.'
            )

    # Fallback to environment variables
    username = config.invictus_user or os.environ.get('INVICTUS_USER')
    password = config.invictus_pass or os.environ.get('INVICTUS_PASS')

    if username and password:
        logger.info('Using credentials from environment variables')
        return username, password

    # Both methods failed
    secret_name = config.invictus_secret_name or "not configured"
    error_msg = (
        'WordPress credentials not found in Secrets Manager or '
        f'environment variables. Secret name: {secret_name}'
    )
    logger.error(error_msg)
    raise ValueError(error_msg)


@lambda_handler
def get_invictus_post(event, context):
    """GET Invictus Weightlifting WP blog post"""
    config = get_config()

    # Retrieve credentials from Secrets Manager (with env var fallback)
    try:
        username, password = get_wordpress_credentials()
        # Credentials are retrieved but not currently used by API service
        # They are available for future use if WordPress API requires auth
        if username and password:
            logger.debug('WordPress credentials retrieved successfully')
    except ValueError as e:
        # If credentials are required in the future, this will raise error
        # For now, we log a warning but continue (API may work without auth)
        logger.warning(f'Could not retrieve WordPress credentials: {str(e)}')
        username, password = None, None

    api_service = InvictusAPIService(config.invictus_weightlifting_api)

    posts_per_page = event.get('posts_per_page', False) or 1
    page_num = event.get('page', False) or 1

    posts = api_service.get_posts(
        posts_per_page=posts_per_page, page=page_num
    )

    # Return posts directly (Step Functions will handle serialization)
    return posts


@lambda_handler
def dump_post_to_bucket(invictus_raw_post, context):
    """Dump Invictus post to S3 bucket with idempotency checks."""
    config = get_config()
    
    post = invictus_raw_post
    post_date_time_obj = parse(post["date"])
    
    bucket_path = 'raw/{posted}__{slug}__raw.json'.format(
        slug=post["slug"], posted=post_date_time_obj.date())
    
    # Initialize services
    s3_service = S3Service(config.invictus_bucket)
    idempotency_service = IdempotencyService(config.idempotency_table)
    
    # Generate idempotency key
    idempotency_key = IdempotencyService.generate_key('dump_post_to_bucket', bucket_path)
    
    # DynamoDB idempotency check: skip if operation already completed
    if idempotency_service.check(idempotency_key):
        logger.info(f'Operation already completed for post "{post["title"]["rendered"]}", skipping')
        return post
    
    # S3 idempotency check: skip write if object already exists
    if s3_service.object_exists(bucket_path):
        logger.info(f'Post "{post["title"]["rendered"]}" already exists in bucket, skipping write')
        # Mark as complete even though we didn't write (object already exists)
        idempotency_service.mark_complete(idempotency_key)
        return post
    
    # Write post to S3
    logger.info('Dumping post "{}" to bucket'.format(post["title"]["rendered"]))
    s3_service.put_json_object(
        bucket_path,
        post,
        metadata={
            'idempotency_key': idempotency_key,
            'operation': 'dump_post_to_bucket'
        }
    )
    
    # Mark operation as complete in idempotency table
    idempotency_service.mark_complete(idempotency_key)
    
    return post


@lambda_handler
def strip_post_html(post, ctx):
    """
    Strip HTML from post content because it's not well structured markup.
    Preserves the post date, slug, and title for downstream processing.
    """
    post_text_raw = BeautifulSoup(
        post['content']['rendered'], 'html.parser')
    
    result = {"text": post_text_raw.get_text()}
    
    # Preserve post date for date calculations in downstream steps
    if 'date' in post:
        result['post_date'] = post['date']
    
    # Preserve slug and title for date range extraction
    if 'slug' in post:
        result['slug'] = post['slug']
    
    if 'title' in post and isinstance(post['title'], dict):
        result['title'] = post['title'].get('rendered', '')
    elif 'title' in post:
        result['title'] = post['title']
    
    return result


@lambda_handler
def save_sessions_to_bucket(session_records, context):
    """Save session records to S3 bucket using standard library"""
    config = get_config()
    
    # Handle decorator-wrapped input (if list was wrapped as {"result": [...]})
    if (isinstance(session_records, dict) and
            'result' in session_records and
            isinstance(session_records['result'], list)):
        records = session_records['result']
    elif isinstance(session_records, list):
        records = session_records
    else:
        # Fallback: try to extract records from dict structure
        fallback = ([session_records]
                    if not isinstance(session_records, list)
                    else session_records)
        records = session_records.get(
            'records', session_records.get('data', fallback))
    
    # Parse dates and find min/max
    dates = []
    for record in records:
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
    
    # Initialize S3 service
    s3_service = S3Service(config.invictus_bucket)
    
    # S3 idempotency check: skip write if file already exists
    if s3_service.object_exists(bucket_path):
        logger.info(f'Weekly sessions file already exists ({start_date} to {end_date}), skipping write')
        return {"records": records}
    
    # Save to bucket as JSON Lines format (one JSON object per line)
    s3_service.put_json_lines(bucket_path, records)
    
    return {"records": records}


@lambda_handler
def sessions_to_json_records_by_day(event, context):
    """
    Wrapper function for sessions_to_json_records_by_day from transforms module.
    Ensures proper Lambda handler format for Step Functions.
    """
    from transforms import sessions_to_json_records_by_day as transform_sessions_to_records
    return transform_sessions_to_records(event, context)


@lambda_handler
def clean_sessions_df_records(event, context):
    """
    Wrapper function for clean_sessions_df_records from transforms module.
    Maintains backward compatibility with functions.yml handler reference.
    """
    from transforms import clean_sessions_df_records as transform_clean_sessions
    return transform_clean_sessions(event, context)
