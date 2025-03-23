
# app.py
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import pandas as pd
import json
import boto3
import tempfile
import io
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from werkzeug.utils import secure_filename

from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global memory store for file data
file_data = {
    'current_file': None,
    'dataframes': {},
    'metadata': {},
    'insights': {}
}

print("AWS_DEFAULT_REGION" + os.getenv('AWS_DEFAULT_REGION'))
bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name=os.getenv('AWS_DEFAULT_REGION'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

# Helper functions
def generate_file_insights(df):
    """Generate insights about the uploaded file"""
    insights = {
        'row_count': len(df),
        'column_count': len(df.columns),
        'columns': list(df.columns),
        'data_types': {col: str(dtype) for col, dtype in df.dtypes.items()},
        'missing_values': df.isnull().sum().to_dict(),
        'numeric_columns': df.select_dtypes(include=['number']).columns.tolist(),
        'categorical_columns': df.select_dtypes(include=['object']).columns.tolist(),
        'sample_data': df.head(5).to_dict()
    }
    return insights

def create_prompt(message, file_insights):
    """Create a prompt for the Titan Text G1 - Lite model"""
    
    # Create the system prompt text
    system_prompt = """
You are an AI assistant specialized in analyzing and explaining Excel data. Your role is to help users understand the data, generate insights, create visualizations, and answer questions about the data.

Instructions:
- Always analyze the data thoroughly before responding
- You can create plots, charts, and tables to visualize data
- If the user asks for Python code, provide executable code with explanations
- Format your responses in markdown for readability
- Include relevant statistics when analyzing numerical data
```

Available Data Information:
{file_insights}
The user has uploaded this Excel file and wants assistance with understanding and analyzing it. Help them with accurate, precise responses based on the data provided.
"""
    
    # Format the system prompt with file insights
    formatted_system_prompt = system_prompt.format(file_insights=json.dumps(file_insights, indent=2))
    
    # Create the combined prompt for Titan
    combined_prompt = formatted_system_prompt + "\n\nUser: " + message
    
    # Titan format uses inputText and textGenerationConfig
    print("combined_prompt: ", combined_prompt)
    prompt = {
        "inputText": combined_prompt,
        "textGenerationConfig": {
            "maxTokenCount": 4096,
            "temperature": 0.7,
            "topP": 0.9,
            "stopSequences": []
        }
    }
    
    return prompt


def generate_plot(df, plot_type, x_column, y_column=None, title=None):
    """Generate a plot using matplotlib and return as base64 image"""
    plt.figure(figsize=(10, 6))
    
    if plot_type == 'bar':
        sns.barplot(x=df[x_column], y=df[y_column] if y_column else df.index)
    elif plot_type == 'line':
        sns.lineplot(x=df[x_column], y=df[y_column] if y_column else df.index)
    elif plot_type == 'scatter':
        sns.scatterplot(x=df[x_column], y=df[y_column])
    elif plot_type == 'histogram':
        sns.histplot(df[x_column])
    elif plot_type == 'pie':
        df[x_column].value_counts().plot(kind='pie')
    
    if title:
        plt.title(title)
    plt.tight_layout()
    
    # Save plot to a bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    
    # Convert to base64
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    return f"data:image/png;base64,{img_str}"

# Routes
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': 'Only Excel (.xlsx) files are supported'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Load the Excel file
        # df = pd.read_excel(filepath, sheet_name=None)
        df = pd.read_excel(filepath, sheet_name=None, engine='openpyxl')
        # Update the file data store
        file_data['current_file'] = filename
        file_data['dataframes'] = {sheet: df_sheet.fillna('').to_dict() for sheet, df_sheet in df.items()}
        
        # Generate metadata and insights
        metadata = {
            'filename': filename,
            'sheets': list(df.keys()),
            'upload_time': pd.Timestamp.now().isoformat()
        }
        file_data['metadata'] = metadata
        
        # Generate insights for each sheet
        insights = {}
        for sheet, df_sheet in df.items():
            insights[sheet] = generate_file_insights(df_sheet)
        file_data['insights'] = insights
        
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': filename,
            'metadata': metadata
        })
    
    except Exception as e:
        print("upload failure: "+e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    if not file_data['current_file']:
        return jsonify({'error': 'No file has been uploaded yet'}), 400

    try:
        data = request.json
        message = data.get('message')
        stream_mode = data.get('stream', False)
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Create the prompt for AWS Bedrock Titan model
        prompt = create_prompt(message, file_data['insights'])
        
        # Handle streaming mode
        if stream_mode:
            return Response(
                stream_response(prompt),
                content_type='text/event-stream'
            )
        else:
            # Non-streaming mode (original code)
            response = bedrock_runtime.invoke_model(
                modelId='amazon.titan-text-lite-v1',
                contentType='application/json',
                accept='application/json',
                body=json.dumps(prompt)
            )
            print("model response: ", response)
            
            # Parse the response - Titan has a different response format
            response_body = json.loads(response['body'].read().decode('utf-8'))
            # Extract text from Titan response format
            ai_response = response_body['results'][0]['outputText']
            
            # Check if response contains a request for plot generation
            if '[[PLOT' in ai_response:
                # Extract plot information
                plot_info = ai_response.split('[[PLOT')[1].split(']]')[0].strip()
                plot_params = json.loads(plot_info)
                
                # Get the specified sheet
                sheet = plot_params.get('sheet', list(file_data['dataframes'].keys())[0])
                df = pd.DataFrame(file_data['dataframes'][sheet])
                
                # Generate the plot
                plot_image = generate_plot(
                    df,
                    plot_params.get('type', 'bar'),
                    plot_params.get('x'),
                    plot_params.get('y'),
                    plot_params.get('title')
                )
                
                # Replace the plot placeholder with the actual image
                ai_response = ai_response.replace(f'[[PLOT{plot_info}]]', f'![{plot_params.get("title", "Plot")}]({plot_image})')
            
            return jsonify({'response': ai_response})

    except Exception as e:
        print("chat error: ", e)
        return jsonify({'error': str(e)}), 500

def stream_response(prompt):
    """Generator function to stream the response from Bedrock"""
    try:
        # Initialize streaming response
        response = bedrock_runtime.invoke_model_with_response_stream(
            modelId='amazon.titan-text-lite-v1',
            contentType='application/json',
            accept='application/json',
            body=json.dumps(prompt)
        )
        
        # Buffer for accumulating text to check for plot requests
        full_response = ""
        
        # Process each chunk as it comes in
        for event in response.get('body'):
            chunk = json.loads(event['chunk']['bytes'].decode('utf-8'))
            
            # For Titan model, extract the text from the chunk
            # The exact chunk format may vary, adjust based on actual response
            chunk_text = ""
            if 'results' in chunk and len(chunk['results']) > 0:
                chunk_text = chunk['results'][0].get('outputText', '')
            elif 'outputText' in chunk:
                chunk_text = chunk.get('outputText', '')
                
            # Add to our buffer
            full_response += chunk_text
            
            # Check if this chunk has plot tags
            # Note: This is simplified - in real use you might need a more
            # sophisticated approach to handle partial plot tags spanning multiple chunks
            if '[[PLOT' in full_response and ']]' in full_response:
                # Process plot request
                processed_text = process_plot_in_streaming(full_response)
                # Update our buffer with processed text
                full_response = processed_text
                
            # Send this chunk to client
            print("streaming: ",chunk_text)
            yield f"data: {json.dumps({'text': chunk_text})}\n\n"
            
    except Exception as e:
        print("Streaming error:", e)
        error_message = {'error': str(e)}
        yield f"data: {json.dumps(error_message)}\n\n"

def process_plot_in_streaming(text):
    """Process plot requests in streaming mode"""
    if '[[PLOT' not in text or ']]' not in text:
        return text
        
    try:
        # Extract plot information
        plot_info = text.split('[[PLOT')[1].split(']]')[0].strip()
        plot_params = json.loads(plot_info)
        
        # Get the specified sheet
        sheet = plot_params.get('sheet', list(file_data['dataframes'].keys())[0])
        df = pd.DataFrame(file_data['dataframes'][sheet])
        
        # Generate the plot
        plot_image = generate_plot(
            df,
            plot_params.get('type', 'bar'),
            plot_params.get('x'),
            plot_params.get('y'),
            plot_params.get('title')
        )
        
        # Replace the plot placeholder with the actual image
        return text.replace(f'[[PLOT{plot_info}]]', f'![{plot_params.get("title", "Plot")}]({plot_image})')
    
    except Exception as e:
        print("Plot processing error:", e)
        # If there's an error, return the original text
        return text
    
    
if __name__ == '__main__':
    app.run(debug=True)