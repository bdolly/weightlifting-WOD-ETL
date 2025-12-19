import os
import json
import requests
import boto3
from bs4 import BeautifulSoup
from transforms import *
from dateutil.parser import parse


s3_resource = boto3.resource('s3')
invictus_api = os.environ['INVICTUS_WEIGHTLIFTING_API']


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

    s3object = s3_resource.Object(os.environ['INVICTUS_BUCKET'], bucket_path)
    print('- Dumping post "{}" to bucket'.format(post["title"]["rendered"]))

    s3object.put(
        Body=(bytes(json.dumps(post).encode('UTF-8')))
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
