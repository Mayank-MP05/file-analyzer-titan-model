import os
import json
import boto3
from dotenv import load_dotenv

def setup_bedrock_client():
    """Set up and return an AWS Bedrock runtime client."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Use environment variables for AWS credentials
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')  # Default to us-east-1 if not specified
    aws_session_token = os.getenv('AWS_SESSION_TOKEN', None)  # Optional session token
    
    # Create and return Bedrock runtime client
    session = boto3.Session(
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        aws_session_token=aws_session_token,
        # region_name=aws_region
    )
    
    return session.client('bedrock-runtime')

def create_deepseek_prompt(message):
    """Create a prompt for the DeepSeek model."""
    prompt = {
        "inferenceConfig": {
            "max_tokens": 512,
            "temperature": 0.7
        },
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ]
    }
    
    return prompt

def invoke_deepseek_model(client, prompt, model_id='arn:aws:bedrock:us-east-1:628290474730:inference-profile/us.deepseek.r1-v1:0'):
    """Invoke the DeepSeek model through AWS Bedrock."""
    try:
        response = client.invoke_model(
            modelId=model_id,
            contentType='application/json',
            accept='application/json',
            body=json.dumps(prompt)
        )
        
        # Parse and return the response
        response_body = json.loads(response['body'].read().decode('utf-8'))
        return response_body
    
    except Exception as e:
        print(f"Error invoking model: {str(e)}")
        return {"error": str(e)}

def main():
    """Main function to test DeepSeek model with a simple prompt."""
    # Set up Bedrock client
    bedrock_client = setup_bedrock_client()
    
    # Simple test prompt
    test_message = "Tell me a brief joke about programming."
    
    # Create prompt for DeepSeek
    prompt = create_deepseek_prompt(test_message)
    
    # Invoke model and get response
    print("Sending request to DeepSeek model...")
    response = invoke_deepseek_model(bedrock_client, prompt)
    
    # Print full response for debugging
    print("\nFull response from Bedrock API:")
    print(json.dumps(response, indent=2))
    
    # Extract and print just the model's text response if available
    if 'output' in response:
        print("\nModel response:")
        print(response['output'])
    elif 'content' in response and response.get('content'):
        print("\nModel response:")
        print(response['content'][0]['text'] if isinstance(response['content'], list) else response['content'])
    
if __name__ == "__main__":
    main()