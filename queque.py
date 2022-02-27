import boto3
import os
import json
import requests
import math

invictus_api_endpoint = os.environ['INVICTUS_WEIGHTLIFTING_API']
invicuts_api_requests_sqs_name = os.environ['INVICTUS_WEIGHTLIFTING_API_QUEQUE_NAME']

_sqs_client = None
_sqs_url = None


def get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client('sqs')
    return _sqs_client


def get_queue_url():
    global _sqs_url
    if _sqs_url is None:
        client = get_sqs_client()
        response = client.get_queue_url(
            QueueName=invicuts_api_requests_sqs_name)
        _sqs_url = response['QueueUrl']
    return _sqs_url


def calc_sqs_items_from_api(event, context):

    posts_per_page = event.get('posts_per_page', False) or 1
    page_num = event.get('page', False) or 1

    api_req = requests.head(
        invictus_api_endpoint+"&per_page=" +
        str(posts_per_page)+"&page="+str(page_num),
        auth=(os.environ['INVICTUS_USER'], os.environ['INVICTUS_PASS'])
    )

    return [{
        "page": idx+1,
        "posts_per_page": posts_per_page
    } for idx, val in
        enumerate(
        [None] * int(api_req.headers["x-wp-totalpages"])
    )]


def push_item_to_queque(event, ctx):
    client = get_sqs_client()
    sqs_url = get_queue_url()

    # batch by pages of 100 messages per minute
    batchPage = math.ceil(int(event["page"])/100)
    delaySecs = batchPage * 60

    event["delaySecs"] = delaySecs
    event["batchPage"] = batchPage

    return client.send_message(
        QueueUrl=sqs_url,
        DelaySeconds=delaySecs,
        MessageBody=json.dumps(event),
    )
