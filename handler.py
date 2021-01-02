import os
import json
import requests
import boto3

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

    bucket_path = '{slug}/_raw_{slug}.json'.format(slug=post["slug"])

    print('- Creating bucket path:  {}'.format(bucket_path))

    s3object = s3_resource.Object(os.environ['INVICTUS_BUCKET'], bucket_path)
    print('- Dumping post "{}" to bucket'.format(post["title"]["rendered"]))

    s3object_success = s3object.put(
        Body=(bytes(json.dumps(post).encode('UTF-8')))
    )

    return json.dumps(post)
