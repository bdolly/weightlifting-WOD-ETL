"""
Lambda handler functions for Invictus Weightlifting WOD ETL pipeline.

This module provides Lambda handlers that use the service layer
for AWS operations and external API calls.
"""
from bs4 import BeautifulSoup
from dateutil.parser import parse
from logger_config import get_logger
from config import get_config
from services.s3_service import S3Service
from services.idempotency_service import IdempotencyService
from services.invictus_api_service import InvictusAPIService
from utils.decorators import lambda_handler

logger = get_logger(__name__)


@lambda_handler
def get_invictus_post(event, context):
    """GET Invictus Weightlifting WP blog post"""
    config = get_config()
    
    api_service = InvictusAPIService(config.invictus_weightlifting_api)
    
    posts_per_page = event.get('posts_per_page', False) or 1
    page_num = event.get('page', False) or 1
    
    posts = api_service.get_posts(posts_per_page=posts_per_page, page=page_num)
    
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
    """
    post_text_raw = BeautifulSoup(
        post['content']['rendered'], 'html.parser')
    
    return {"text": post_text_raw.get_text()}


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
def clean_sessions_df_records(event, context):
    """
    Wrapper function for clean_sessions_df_records from transforms module.
    Maintains backward compatibility with functions.yml handler reference.
    """
    from transforms import clean_sessions_df_records as transform_clean_sessions
    return transform_clean_sessions(event, context)
