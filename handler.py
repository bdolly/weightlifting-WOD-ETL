import os
import json
import requests
# from bs4 import BeautifulSoup

invictus_api = os.environ['INVICTUS_WEIGHTLIFTING_API']

def GET_invictus_post(user_name, password, posts=1):
    """GET Invicitus Weightlifting WP blog post"""

    api_req = requests.get(
        invictus_api+"&per_page="+str(posts), 
        auth=(user_name,password)
    )

    return api_req.json()
    


def hello(event, context):

    response = json.dumps(
                    GET_invictus_post(os.environ['INVICTUS_USER'], os.environ['INVICTUS_PASS'])
                )

    return response
    

    # Use this code if you don't use the http event with the LAMBDA-PROXY
    # integration
    """
    return {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "event": event
    }
    """


    
    

