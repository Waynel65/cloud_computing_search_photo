import boto3
import json
import urllib3

def get_secret():

    secret_name = "opensearch/master"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = json.loads(get_secret_value_response['SecretString'])
    
    return secret
    
def set_photo_object(key, labels):
    """
        package up the photo type specified by the API
    """
    photo = {
        "url": f"https://hw2-photo-bucket-b2.s3.amazonaws.com/{key}",
        "labels": labels
    }
    
    return photo

def set_response_object(es_photos):
    """
        given a list of objects scrapped from ES
        package them into proper format for the API
        to consume
    """
    resp = []
    for photo in es_photos:
        key = photo["_source"]["objectKey"]
        labels = photo["_source"]["labels"]
        
        photo_object = set_photo_object(key, labels)
        resp.append(photo_object)
    
    return resp
    

def parse_query_keywords(response):
    """
        upon receiving response from Lex
        Extract the keywords from user's query
    """
    res = []
    values = response["interpretations"][0]["intent"]["slots"]["PhotoSubject"]["values"]
    for val in values:
        res.append(val["value"]["interpretedValue"])
    
    return res
    
def search_ES(keywords):
    """
        using the keywords got from user
        search in ES the photos with relevant labels
    """
    secret = get_secret()
    http = urllib3.PoolManager()
    headers = urllib3.make_headers(basic_auth='wayne'+':'+ secret['wayne'])
    headers["Content-Type"] = "application/json"
    
    endpoint = "https://vpc-photos-ggjle4o6uthzcmenkdypvduzy4.us-east-1.es.amazonaws.com"
    index_name = "photo_index"
    
    query = {
        "query": {
            "bool": {
                "must": [{"match": {"labels": keyword}} for keyword in keywords]
            }
        }
    }
    
    response = http.request(
        "GET",
        f"{endpoint}/{index_name}/_search",
        headers=headers,
        body=json.dumps(query)
    )
    
    results = json.loads(response.data.decode("utf-8"))
    print(results["hits"]["hits"])
    
    return results["hits"]["hits"]


def close(message):
    response = {
      "sessionState": {
        "dialogAction": {
          "type": "Close"
        },
        "intent": {
          "confirmationState": "Confirmed",
          "name": "SearchIntent",
          "state": "Fulfilled",
        },
      },
      "messages": [
        {
          "contentType": "PlainText",
          "content": message,
        }
      ]
    }

    return response
    
def build_msg_params(msg):
  return {
    'botId': '76WV740PIT',
    'botAliasId': 'TSTALIASID',
    'text': msg,
    'localeId': 'en_US',
    'sessionId': 'test-session'
  }


def get_user_query(event):
    query = event["queryStringParameters"]["q"]
    lex_client = boto3.client('lexv2-runtime')
    lex_params = build_msg_params(query)
    
    keywords = None
    success = True
    try:
        response = lex_client.recognize_text(**lex_params)
        # add error handling
        print("lex response", response)
        keywords = parse_query_keywords(response)
        print("parsed results:", keywords)
        return success, keywords
    except:
        return False, None

def return_error(error_msg):
    response = {
        "statusCode": 500,
        "headers": {
            # "Content-Type": "application/json",
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
       "body": json.dumps({
            "message": error_msg
        })
    }
    
    return response

def lambda_handler(event, context):
    print("event", event)
    success, keywords = get_user_query(event)
    if not success:
        print("something went wrong with lex")
        return return_error("something went wrong with lex")
    print("got keywords: ", keywords)
    
    resp = set_response_object(search_ES(keywords)) if keywords else []

    
    response = {
        "statusCode": 200,
        "headers": {
            # "Content-Type": "application/json",
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
       "body": json.dumps({
            "results": resp
        })
    }
    
    return response
    
