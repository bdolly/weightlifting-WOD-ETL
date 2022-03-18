import os
import json
import requests
import boto3
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from transforms import *
from utils import get_secret
import athena_from_s3
from dateutil.parser import parse
from datetime import datetime, timedelta, date


s3_resource = boto3.resource('s3')
invictus_api = os.environ['INVICTUS_WEIGHTLIFTING_API']
# athena_client = boto3.client('athena')


def GET_invictus_post(event, context):
    """GET Invicitus Weightlifting WP blog post"""
    secrets = get_secret("dev/InvictusServices/wp-api",
                         os.environ["aws_region"])

    _secrets = json.loads(secrets)

    posts = event["Records"][0]
    post = json.loads(posts.get('body', False)) or event

    posts_per_page = post.get('posts_per_page', False) or 1
    page_num = post.get('page', False) or 1
    print("GET {} ".format(invictus_api+"&per_page=" +
                           str(posts_per_page)+"&page="+str(page_num)))
    api_req = requests.get(
        invictus_api+"&per_page="+str(posts_per_page)+"&page="+str(page_num),
        auth=(_secrets['INVICTUS_USER'], _secrets['INVICTUS_PASS'])
    )

    return api_req.json()


def trigger_staging_statemachine(event, context):
    print(event)
    client = boto3.client('stepfunctions')
    response = client.start_execution(
        stateMachineArn=os.environ['statemachine_arn'],
        # name='string',
        input=json.dumps(event, default=str),
    )
    print(response)


def dump_post_to_bucket(invictus_raw_post, context):

    post = invictus_raw_post[0]
    post_date_time_obj = parse(post["date"])

    # TODO: get yyyy-mm-dd from post["date"] to use as partition
    partition = re.sub('-', '/', str(post_date_time_obj.date()))
    # add a partition key to our post so that we can project athena partitions
    post["date_partition"] = partition

    bucket_path = 'raw/{partition}/{posted}__{slug}__raw.json'.format(partition=partition,
                                                                      slug=post["slug"], posted=post_date_time_obj.date())

    s3object = s3_resource.Object(os.environ['INVICTUS_BUCKET'], bucket_path)
    print(
        '- Dumping post "{title}" to bucket: {bucket}'.format(
            title=post["title"]["rendered"], bucket=bucket_path)
    )

    s3object_success = s3object.put(
        Body=(bytes(json.dumps(post).encode('UTF-8')))
    )

    if not s3object_success:
        return None

    return post


def strip_post_html(post, ctx):
    """
        strip HTML from post conent because it's not well structured markup.
    """

    post_text_raw = BeautifulSoup(
        post['content']['rendered'], 'html.parser')

    return post_text_raw.get_text()


def save_sessions_to_bucket(session_records, context):

    df = pd.DataFrame(session_records)
    df['date'] = pd.to_datetime(
        df['date'], infer_datetime_format=True)

    bucket_path = 'weekly/{start_date}__{end_date}--5-day-weightlifting-program.json'.format(
        start_date=df["date"].min().date(), end_date=df["date"].max().date())

    df['date'] = df['date'].dt.strftime('%Y-%m-%d')

    s3object = s3_resource.Object(os.environ['INVICTUS_BUCKET'], bucket_path)

    # # save to bucket as lines of json so that we can query it using S3 select
    s3object_success = s3object.put(
        Body=(
            str(df.to_json(orient="records", lines=True))
        )
    )

    return df.to_json(orient="records")


def query_for_workout_this_week(event, context):

    day = date.today().strftime("%Y/%m/%d")
    dt = datetime.strptime(day, '%Y/%m/%d')
    # start on a sunday
    start = dt - timedelta(days=dt.weekday()) - timedelta(days=1)
    # end on a sat
    end = start + timedelta(days=6)
    start_partition = start.strftime('%Y/%m/%d')
    end_partition = end.strftime('%Y/%m/%d')

    session = boto3.Session()

    query = f"SELECT date_partition, content.rendered FROM {os.environ['athena_db']}.raw_posts WHERE date_partition >= '{start_partition}' and date_partition <= '{end_partition}'"

    params = {
        'region': os.environ["aws_region"],
        'database': os.environ["athena_db"],
        'bucket': os.environ['athena_output_bucket'],
        'path': 'temp/',
        'query': query
    }
    print(params)

    # Fucntion for obtaining query results and location
    location, data = athena_from_s3.query_results(session, params)
    print("Locations: ", location)
    print("Result Data: ")
    print(data)
    return data
