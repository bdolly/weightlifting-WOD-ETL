import os
import json
import requests
import boto3
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from transforms import *
from dateutil.parser import parse


s3_resource = boto3.resource('s3')
invictus_api = os.environ['INVICTUS_WEIGHTLIFTING_API']


def GET_invictus_post(event, context):
    """GET Invicitus Weightlifting WP blog post"""

    api_req = requests.get(
        invictus_api+"&per_page="+str(1),
        auth=(os.environ['INVICTUS_USER'], os.environ['INVICTUS_PASS'])
    )

    return api_req.json()


def dump_post_to_bucket(invictus_raw_posts, context):

    post = invictus_raw_posts[0]
    post_date_time_obj = parse(post["date"])

    bucket_path = 'raw/{posted}__{slug}__raw.json'.format(
        slug=post["slug"], posted=post_date_time_obj.date())

    s3object = s3_resource.Object(os.environ['INVICTUS_BUCKET'], bucket_path)
    print('- Dumping post "{}" to bucket'.format(post["title"]["rendered"]))

    s3object_success = s3object.put(
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

    df = pd.DataFrame(session_records, columns=session_records[0].keys())
    df['date'] = pd.to_datetime(
        df['date'], infer_datetime_format=True)

    bucket_path = 'weekly/{start_date}__{end_date}--5-day-weightlifting-program.json'.format(
        start_date=df["date"].min().date(), end_date=df["date"].max().date())

    df['date'] = df['date'].dt.strftime('%Y-%m-%d')

    s3object = s3_resource.Object(os.environ['INVICTUS_BUCKET'], bucket_path)

    # save to bucket as lines of json so that we can query it using S3 select
    s3object_success = s3object.put(
        Body=(
            str(df.to_json(orient="records", lines=True))
        )
    )

    return df.to_json()
