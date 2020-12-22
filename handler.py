import os
import json
import requests
import boto3

s3_resource = boto3.resource('s3')
invictus_api = os.environ['INVICTUS_WEIGHTLIFTING_API']

def GET_invictus_post(user_name, password, posts=1):
    """GET Invicitus Weightlifting WP blog post"""

    api_req = requests.get(
        invictus_api+"&per_page="+str(posts), 
        auth=(user_name,password)
    )

    return api_req.json()
    


def dump_post_to_bucket(event, context):

    response = GET_invictus_post(os.environ['INVICTUS_USER'], os.environ['INVICTUS_PASS'])[0]
    
    workout_slug = response["slug"]

    s3object = s3_resource.Object(os.environ['INVICTUS_BUCKET'], '{slug}/_raw_{slug}.json'.format(slug=workout_slug))
    
    return s3object.put(
        Body=(bytes(json.dumps(response).encode('UTF-8')))
    )
    