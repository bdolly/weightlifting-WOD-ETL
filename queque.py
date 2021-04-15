import boto3
import os
import json
import requests
from handler import GET_invictus_post, dump_post_to_bucket

invictus_api_endpoint = os.environ['INVICTUS_WEIGHTLIFTING_API']
invicuts_api_requests_sqs_name = os.environ['INVICTUS_WEIGHTLIFTING_API_QUEQUE_NAME']

_sqs_client = None
_s3_client = None
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

    # total number of wp api resutls pages
    total_pages = round(
        int(api_req.headers["X-WP-Total"])/posts_per_page)

    return [{
        "page": idx+1,
        "posts_per_page": posts_per_page
    } for idx, val in
        enumerate(
        [None] * total_pages
    )]


def push_item_to_queque(event, ctx):
    client = get_sqs_client()
    sqs_url = get_queue_url()

    return client.send_message(
        QueueUrl=sqs_url,
        MessageBody=json.dumps(event))


def process_queque_item(event, ctx):
    sqs = get_sqs_client()
    sqs_url = get_queue_url()

    # grab single sqs item
    response = sqs.receive_message(
        QueueUrl=sqs_url,
        MaxNumberOfMessages=1,
    )

    messages = response.get('Messages')

    if not messages:
        return "No Messages found in {}".format(sqs_url)

    receipt = messages[0].get('ReceiptHandle')

    request_params = json.loads(
        messages[0].get('Body', {})
    )

    posts = GET_invictus_post(request_params, {})

    processed = []

    for post in posts:
        success = dump_post_to_bucket(post, {})
        if success:
            processed.append(success["title"]["rendered"])

    if(len(processed) == len(posts)):
        sqs.delete_message(QueueUrl=sqs_url, ReceiptHandle=receipt)

    return processed
