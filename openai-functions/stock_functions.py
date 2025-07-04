# stock_functions.py by Zubeyr

import json
import requests
import time
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_KEY = os.getenv("FINNHUB_API_KEY")

# Your stock functions
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
    