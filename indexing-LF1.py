import json
import urllib.parse
import boto3
import urllib3
import time

print('Loading function')


def detect_labels(photo, bucket):
    """ calling the rekognition service
        TODO: research on how this works
    """
    rekognition_client = boto3.client('rekognition')
    
    # # Replace with your S3 bucket name and object key
    
    # bucket = 'hw2-photo-bucket-b2'
    # key = 'cars.png'

    response = rekognition_client.detect_labels(
        Image={
            'S3Object': {
                'Bucket': bucket,
                'Name': photo
            }
        },
        MaxLabels=10,
        MinConfidence=80
    )
    print("[O] Connected to Rekognition")
   
    print('Detected labels for ' + photo)
    res = []
    for label in response['Labels']:
        res.append(label['Name'])
        print("Label: " + label['Name'])
        print("Confidence: " + str(label['Confidence']))
        print("Instances:")
    
    
    return res

def retrieve_metadata(s3_client, bucket, key):
    response = s3_client.head_object(Bucket=bucket, Key=key)
    metadata = response['Metadata']['customlabels']
    metadata_arr = metadata.split(", ")
    
    print("custom metadata: ", metadata_arr)
    return metadata_arr

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


def create_index():
    """
        need to create an index first
        THIS FUNCTION SHOULD ONLY RUN ONCE
    """
    secret = get_secret()
    headers = urllib3.make_headers(basic_auth='wayne'+':'+ secret['wayne'])
    headers["Content-Type"] = "application/json"
    
    endpoint = "https://vpc-photos-ggjle4o6uthzcmenkdypvduzy4.us-east-1.es.amazonaws.com"
    index_name = "photo_index"
    url = f"{endpoint}/{index_name}"
    http = urllib3.PoolManager()
    
    response = http.request("PUT", url, headers=headers)
    print("Create index response:", response.data.decode("utf-8"))
    
    return

def index_exists():
    endpoint = "https://vpc-photos-ggjle4o6uthzcmenkdypvduzy4.us-east-1.es.amazonaws.com"
    index_name = "photo_index"
    url = f"{endpoint}/{index_name}"
    http = urllib3.PoolManager()
    response = http.request("HEAD", url)
    return response.data.decode.status == 200 # this line does not work

def store_to_ES(key, bucket, labels):
    """
        store photo info in ES
    """
    secret = get_secret()
    labels = [l.lower() for l in labels]
    
    http = urllib3.PoolManager()
    headers = urllib3.make_headers(basic_auth='wayne'+':'+ secret['wayne'])
    headers["Content-Type"] = "application/json"
    endpoint = "https://vpc-photos-ggjle4o6uthzcmenkdypvduzy4.us-east-1.es.amazonaws.com"
    index_name = "photo_index"
    
    # doc_id = key
    document = {
        "objectKey": key,
        "bucket": bucket,
        "createTimestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "labels": labels
    }
    print("this will be uploaded to ES", document)
    url = f"{endpoint}/{index_name}/_doc"
    
    body = json.dumps(document)
    
    response = http.request('POST', url, headers=headers, body=body)
    
    return response.status
    
def search_labels_ES(query):
    """
        extract keywords from query input by user
        search in ES the photos that contain these relevant labels
        
    """
    
def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    s3 = boto3.client('s3')

    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        print("[O] Connected to S3")
        metadata_arr = retrieve_metadata(s3, bucket, key)
        ## TODO: add metadata into labels_detected and store in ES
        labels_detected = detect_labels(photo=key, bucket=bucket)
        labels_detected.extend(metadata_arr)
        print("labels detected: ", labels_detected)
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e
    
    success = store_to_ES(key, bucket, labels_detected)
    print("indexing successfully?", success)
    
    response = {
        "statusCode": 200,
         "body": "image uploaded and indexed"
    #     "headers": {
    #         # "Content-Type": "application/json",
    #         'Access-Control-Allow-Headers': 'Content-Type',
    #         'Access-Control-Allow-Origin': '*',
    #         'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
    #     },
    }
    
    return response
