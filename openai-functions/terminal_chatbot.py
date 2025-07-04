# --------------------------------------------------------------
# Import Modules 
# --------------------------------------------------------------

from dotenv import load_dotenv 
import os 
import json
import requests
import pandas as pd 
import time
from datetime import datetime, timedelta
from langchain_community.chat_models import ChatOpenAI
from openai import OpenAI as OpenAIClient   
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain.tools import BaseTool
from langchain.memory import ConversationBufferMemory 
from typing import Optional, Type
from pydantic import BaseModel, Field


# --------------------------------------------------------------
# Load API Tokens From the .env File
# --------------------------------------------------------------

load_dotenv()  
# ✅ Define OpenAI client
client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))

# Finnhub API key
API_KEY = os.getenv("FINNHUB_API_KEY")

# --------------------------------------------------------------
# Define Stock Data Functions (Using Finnhub)
# --------------------------------------------------------------

def get_stock_quote(symbol):
    """Fetch the latest stock price for a given symbol."""
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        stock_info = response.json()
        return json.dumps(stock_info, indent=2)
    else:
        return json.dumps({"error": "Failed to fetch stock data."}, indent=2)

def get_stock_trend(symbol, interval):
    """
    Fetch real trend data for a stock over a specific interval.
    
    Args:
        symbol: The stock ticker symbol
        interval: Time interval (e.g., '5min', '15min', '1hour', '1day')
    """
    # Convert the interval to what Finnhub expects
    interval_mapping = {
        '5min': '5',
        '15min': '15',
        '30min': '30',
        '1hour': '60',
        '4hour': '240',
        '1day': 'D',
        '1week': 'W'
    }
    
    # Default to 1 day if interval not recognized
    resolution = interval_mapping.get(interval, 'D')
    
    # Calculate from/to timestamps
    end_time = datetime.now()
    
    # Determine time range based on interval
    if '5min' in interval or '15min' in interval or '30min' in interval:
        start_time = end_time - timedelta(hours=24)  # Last 24 hours for small intervals
    elif '1hour' in interval or '4hour' in interval:
        start_time = end_time - timedelta(days=7)    # Last week for hourly data
    elif '1day' in interval:
        start_time = end_time - timedelta(days=30)   # Last month for daily data
    elif '1week' in interval:
        start_time = end_time - timedelta(days=365)  # Last year for weekly data
    else:
        start_time = end_time - timedelta(days=7)    # Default to a week
    
    # Convert to Unix timestamp (seconds)
    from_timestamp = int(time.mktime(start_time.timetuple()))
    to_timestamp = int(time.mktime(end_time.timetuple()))
    
    # Build the URL
    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution={resolution}&from={from_timestamp}&to={to_timestamp}&token={API_KEY}"
    
    # Make the API request
    response = requests.get(url)
    if response.status_code == 200:
        trend_data = response.json()
        
        # Check if we got valid data
        if trend_data.get('s') == 'no_data':
            return json.dumps({
                "error": "No data available for the specified parameters",
                "symbol": symbol,
                "interval": interval
            }, indent=2)
            
        # Process the candle data to make it more readable
        processed_data = {
            "symbol": symbol,
            "interval": interval,
            "start_date": start_time.strftime('%Y-%m-%d %H:%M:%S'),
            "end_date": end_time.strftime('%Y-%m-%d %H:%M:%S'),
            "candles": []
        }
        
        # Process data points (c=close, h=high, l=low, o=open, t=timestamp, v=volume)
        timestamps = trend_data.get('t', [])
        opens = trend_data.get('o', [])
        highs = trend_data.get('h', [])
        lows = trend_data.get('l', [])
        closes = trend_data.get('c', [])
        volumes = trend_data.get('v', [])
        
        for i in range(min(len(timestamps), 20)):  # Limit to 20 data points to keep response manageable
            timestamp = datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d %H:%M:%S')
            processed_data["candles"].append({
                "timestamp": timestamp,
                "open": opens[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "volume": volumes[i]
            })
            
        # Add summary statistics
        if closes:
            processed_data["summary"] = {
                "first_price": closes[0],
                "last_price": closes[-1],
                "change": closes[-1] - closes[0],
                "percent_change": ((closes[-1] - closes[0]) / closes[0]) * 100,
                "high": max(highs),
                "low": min(lows),
            }
            
        return json.dumps(processed_data, indent=2)
    else:
        return json.dumps({
            "error": f"Failed to fetch trend data. Status code: {response.status_code}",
            "symbol": symbol,
            "interval": interval
        }, indent=2)

def get_stock_history(symbol, start_date, end_date):
    """
    Fetch historical stock data for a given symbol and date range.
    
    Args:
        symbol: The stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """ 
    # Convert dates to Unix timestamps
    try:
        start_timestamp = int(time.mktime(datetime.strptime(start_date, "%Y-%m-%d").timetuple()))
        end_timestamp = int(time.mktime(datetime.strptime(end_date, "%Y-%m-%d").timetuple()))
    except ValueError:
        return json.dumps({
            "error": "Invalid date format. Please use YYYY-MM-DD format.",
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date
        }, indent=2)
    
    # Build the URL - using daily resolution for historical data
    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&from={start_timestamp}&to={end_timestamp}&token={API_KEY}"
    
    # Make the API request
    response = requests.get(url)
    if response.status_code == 200:
        history_data = response.json()
        
        # Check if we got valid data
        if history_data.get('s') == 'no_data':
            return json.dumps({
                "error": "No historical data available for the specified parameters",
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date
            }, indent=2)
            
        # Process the historical data to make it more readable
        processed_data = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "days": []
        }
        
        # Process data points
        timestamps = history_data.get('t', [])
        opens = history_data.get('o', [])
        highs = history_data.get('h', [])
        lows = history_data.get('l', [])
        closes = history_data.get('c', [])
        volumes = history_data.get('v', [])
        
        for i in range(len(timestamps)):
            date = datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d')
            processed_data["days"].append({
                "date": date,
                "open": opens[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "volume": volumes[i]
            })
            
        # Add summary statistics
        if closes:
            processed_data["summary"] = {
                "start_price": closes[0],
                "end_price": closes[-1],
                "change": closes[-1] - closes[0],
                "percent_change": ((closes[-1] - closes[0]) / closes[0]) * 100,
                "period_high": max(highs),
                "period_high_date": processed_data["days"][highs.index(max(highs))]["date"],
                "period_low": min(lows),
                "period_low_date": processed_data["days"][lows.index(min(lows))]["date"],
                "total_days": len(processed_data["days"])
            }
            
        return json.dumps(processed_data, indent=2)
    else:
        return json.dumps({
            "error": f"Failed to fetch historical data. Status code: {response.status_code}",
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date
        }, indent=2) 
    

# --------------------------------------------------------------
# Function Map for Dynamic Calling
# --------------------------------------------------------------

function_map = {
    "get_stock_quote": get_stock_quote, 
    "get_stock_trend": get_stock_trend, 
    "get_stock_history": get_stock_history, 
}

# --------------------------------------------------------------
# Function Descriptions for OpenAI API
# --------------------------------------------------------------

function_descriptions_multiple = [
    {
        "name": "get_stock_quote",
        "description": "Fetches the latest stock price for a given company.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol, e.g., AAPL for Apple Inc.",
                }
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_stock_trend",
        "description": "Fetches the stock trend data over a recent period.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol, e.g., TSLA for Tesla Inc.",
                },
                "interval": {
                    "type": "string",
                    "description": "Time interval for trend data, e.g., '5min', '15min', '1hour', '1day', '1week'.",
                },
            },
            "required": ["symbol", "interval"],
        },
    },
    {
        "name": "get_stock_history",
        "description": "Retrieves past stock prices over a specified period.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol, e.g., MSFT for Microsoft.",
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date for historical data (format: YYYY-MM-DD).",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date for historical data (format: YYYY-MM-DD).",
                },
            },
            "required": ["symbol", "start_date", "end_date"],
        },
    },
]

# --------------------------------------------------------------
# Run Stock Analysis Chatbot
# --------------------------------------------------------------

def run_stock_analysis_chatbot():
    """
    Run an interactive command-line chatbot for stock analysis.
    """
    print("\n========================================")
    print("🤖 Stock Analysis Chatbot 📈")
    print("Ask questions about stocks, prices, trends, or historical data.")
    print("Type 'exit' to quit the conversation.")
    print("========================================\n")
    
    # Initialize message history
    message_history = [
        {
            "role": "system",
            "content": """You are a helpful financial analysis assistant. 
            When providing stock data, analyze what the numbers mean in simple terms.
            Explain trends, provide context, and highlight the most important insights.
            Remember previous questions to maintain context in the conversation.
            Provide analysis of whether the stock is performing well or not.
            Suggest what this might mean for investors."""
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
                functions=function_descriptions_multiple,
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
                        {"role": "system", "content": "Analyze this data and explain what it means in simple terms. Refer to previous questions if relevant. Explain what the data suggests about the stock's performance and what it might mean for investors."}
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
    run_stock_analysis_chatbot()
