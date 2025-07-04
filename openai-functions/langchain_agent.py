# --------------------------------------------------------------
# Import Modules 
# --------------------------------------------------------------

from dotenv import load_dotenv 
import os 
import json
import requests
from datetime import datetime, timedelta
from openai import OpenAI

# --------------------------------------------------------------
# Load API Tokens From the .env File
# --------------------------------------------------------------

load_dotenv()  
# Define OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# API authentication
API_KEY = os.getenv("VEMCOUNT_API_KEY")
BEARER_TOKEN = os.getenv("VEMCOUNT_BEARER_TOKEN")

# --------------------------------------------------------------
# Define Store Traffic Data Functions
# --------------------------------------------------------------

def get_store_traffic(location_id, period="this_week"):
    """Fetch foot traffic data (count_in) for a given store location."""
    url = f"http://vemcount.test/api/v3/auth/login?api_key={API_KEY}"  
    
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
    }
    
    
    form_data = {
        "source": "locations",
        "data": location_id,
        "period": period,
        "data_output": "count_in"
    }
    
    response = requests.post(url, headers=headers, data=form_data)
    if response.status_code == 200:
        traffic_info = response.json()
        return json.dumps(traffic_info, indent=2)
    else:
        return json.dumps({"error": f"Failed to fetch store traffic data. Status code: {response.status_code}"}, indent=2)

# --------------------------------------------------------------
# Function Map for Dynamic Calling
# --------------------------------------------------------------

function_map = {
    "get_store_traffic": get_store_traffic
}

# --------------------------------------------------------------
# Function Descriptions for OpenAI API
# --------------------------------------------------------------

function_descriptions = [
    {
        "name": "get_store_traffic",
        "description": "Fetches visitor count data (people entering the store) for a specific location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location_id": {
                    "type": "string",
                    "description": "Store location identifier",
                },
                "period": {
                    "type": "string",
                    "description": "Time period for data",
                    "enum": ["yesterday", "this_week", "last_week", "this_month", "last_month"],
                    "default": "this_week"
                }
            },
            "required": ["location_id"],
        },
    }
]

# --------------------------------------------------------------
# Run Store Traffic Analysis Chatbot
# --------------------------------------------------------------

def run_store_traffic_chatbot():
    """
    Run an interactive command-line chatbot for store traffic analysis.
    """
    print("\n========================================")
    print("🏪 Store Traffic Analysis Assistant 👥")
    print("Ask questions about store visitor counts and traffic patterns.")
    print("Type 'exit' to quit the conversation.")
    print("========================================\n")
    
    # Initialize message history
    message_history = [
        {
            "role": "system",
            "content": """You are a helpful retail analytics assistant focused on store traffic data. 
            When providing visitor count data, analyze what the numbers mean in simple terms.
            Explain trends in foot traffic, identify busy/slow periods, and highlight important patterns.
            Remember previous questions to maintain context in the conversation.
            Provide analysis of whether the visitor numbers suggest good store performance.
            Suggest what traffic patterns might mean for staffing, promotions, and store layout."""
        }
    ]
    
    while True:
        user_prompt = input("\n👤 You: ")
        
        if user_prompt.lower() in ['exit', 'quit', 'bye']:
            print("\n🤖 Assistant: Goodbye! Have a great day!")
            break
        
        # Add user message to history
        message_history.append({"role": "user", "content": user_prompt})
        
        try:
            print("\n🔄 Processing...")
            
            output = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=message_history,
                functions=function_descriptions,
                function_call="auto",
            )
            
            message = output.choices[0].message
            
            if hasattr(message, 'function_call') and message.function_call:
                function_name = message.function_call.name
                arguments_json = message.function_call.arguments
                arguments = json.loads(arguments_json)
                
                print(f"📊 Retrieving {function_name} data...")
                
                # Add assistant's function call to history
                message_history.append({
                    "role": "assistant", 
                    "content": None,
                    "function_call": {
                        "name": function_name,
                        "arguments": arguments_json
                    }
                })
                
                # Call the function
                result = function_map[function_name](**arguments)
                
                # Add function result to history
                message_history.append({
                    "role": "function", 
                    "name": function_name, 
                    "content": result
                })
                
                # Get final response with function result
                final_response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=message_history + [
                        {"role": "system", "content": "Analyze this traffic data and explain what it means in simple terms. Refer to previous questions if relevant. Explain what the data suggests about the store's performance and visitor patterns."}
                    ],
                )
                
                final_content = final_response.choices[0].message.content
                print(f"\n🤖 Assistant: {final_content}")
                
                # Add assistant's response to history
                message_history.append({"role": "assistant", "content": final_content})
                
            else:
                print(f"\n🤖 Assistant: {message.content}")
                
                # Add assistant's response to history
                message_history.append({"role": "assistant", "content": message.content})
                
        except Exception as e:
            error_message = f"Sorry, I encountered an error: {str(e)}"
            print(f"\n🤖 Assistant: {error_message}")
            
            # Add error response to history
            message_history.append({"role": "assistant", "content": error_message})

# --------------------------------------------------------------
# Run the chatbot if this script is executed directly
# --------------------------------------------------------------

if __name__ == "__main__":
    run_store_traffic_chatbot()