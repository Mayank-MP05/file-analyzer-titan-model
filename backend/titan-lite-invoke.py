import boto3
import json
import os
from dotenv import load_dotenv

def invoke_titan_text_g1_lite(prompt, max_tokens=512, temperature=0.7):
    """
    Invoke the Amazon Titan Text G1 - Lite model through AWS Bedrock.
    
    Args:
        prompt (str): The input text prompt
        max_tokens (int): Maximum number of tokens to generate
        temperature (float): Controls randomness (0.0-1.0)
        
    Returns:
        dict: The response from the model
    """
    # Load environment variables
    load_dotenv()
    
    # Use environment variables for AWS credentials
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')  # Default to us-east-1 if not specified
    aws_session_token = os.getenv('AWS_SESSION_TOKEN')  # Optional session token
    
    # Create AWS session
    session = boto3.Session(
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        aws_session_token=aws_session_token,
        region_name=aws_region
    )
    
    # Create Bedrock runtime client from session
    bedrock_runtime = session.client(service_name='bedrock-runtime')
    
    # Prepare the request body
    request_body = {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": max_tokens,
            "temperature": temperature,
            "topP": 0.9,
            "stopSequences": []
        }
    }
    
    try:
        # Invoke the model
        response = bedrock_runtime.invoke_model(
            modelId='amazon.titan-text-lite-v1',  # Model ID for Titan Text G1 - Lite
            body=json.dumps(request_body)
        )
        
        # Parse the response
        response_body = json.loads(response['body'].read())
        return response_body
    except Exception as e:
        print(f"Error invoking Titan model: {e}")
        return None

# Example usage
if __name__ == "__main__":
    prompt = "Explain quantum computing in simple terms."
    response = invoke_titan_text_g1_lite(prompt)
    
    # Print the generated text if response was successful
    if response and 'results' in response and len(response['results']) > 0:
        print(response['results'][0]['outputText'])
    else:
        print("Failed to get response from model")