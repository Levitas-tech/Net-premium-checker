#!/usr/bin/env python3
"""
Kite WebSocket with instruments from CSV
Downloads Kite instruments CSV and subscribes to all available options for the nearest expiry
"""

import json
import requests
import queue
import pyotp
import sys
import time as tm
from datetime import datetime, date, timedelta
from urllib import parse
from urllib.parse import parse_qs, urlparse
import urllib
import psycopg2
import re
import threading
from kiteconnect import KiteConnect, KiteTicker
import logging
from psycopg2.extras import RealDictCursor
import pandas as pd
import os
import pytz

# Global variables
kite_instrument_mapping = {}  # Kite instrument_token to kite_symbol mapping
kite_instrument_details = {}  # Kite symbol to instrument details (strike, option_type) mapping
spot_instrument_tokens = {}  # Spot price instrument tokens for each trade_symbol
nearest_expiry_dates = {}  # Nearest expiry dates for each trade_symbol
zerodha_connected = True
db_lock = threading.Lock()
tick_queue = queue.Queue()
shutdown_event = threading.Event()
reconnect_attempts = 0
MAX_RECONNECTS = 10
kite_access_token = None  # Global variable for Zerodha access token
last_activity_time = tm.time()  # Track last WebSocket activity
delay_stats = {'count': 0, 'total_delay': 0, 'min_delay': float('inf'), 'max_delay': 0}  # Track delay statistics

# Global variables for WebSocket control
websocket_running = False
websocket_thread = None
websocket_trade_symbols = []

# Timezone for market-hours determination
IST = pytz.timezone('Asia/Kolkata')

def get_db_connection_params():
    """Get database connection parameters from environment variables"""
    return {
        'host': os.getenv("PGHOST", "localhost"),
        'port': os.getenv("PGPORT", "5432"),
        'dbname': os.getenv("PGDATABASE", "database_name"),
        'user': os.getenv("PGUSER", "username"),
        'password': os.getenv("PGPASSWORD", "password")
    }

def _is_market_hours_now() -> bool:
    try:
        now = datetime.now(IST)
        if now.weekday() >= 5:
            return False
        start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        stop = now.replace(hour=15, minute=31, second=0, microsecond=0)
        return start <= now <= stop
    except Exception:
        return False

# Zerodha credentials
creds = {
    'user_id': '',
    'password': '',
    'totp_key': '',
    'api_key': '',
    'api_secret': ''
}

def download_kite_instruments():
    """Download Kite instruments CSV and save as kite_instruments.csv"""
    try:
        # Delete existing file if it exists
        if os.path.exists("kite_instruments.csv"):
            os.remove("kite_instruments.csv")
            print("🗑️ Deleted existing kite_instruments.csv")
        
        # Download the CSV
        url = "https://api.kite.trade/instruments"
        response = requests.get(url)
        response.raise_for_status()
        
        # Save to file
        with open("kite_instruments.csv", "w") as f:
            f.write(response.text)
        
        print("✅ Downloaded kite_instruments.csv successfully")
        return True
    except Exception as e:
        print(f"❌ Error downloading kite_instruments.csv: {e}")
        return False

def parse_kite_instruments(trade_symbol):
    """Parse kite_instruments.csv and return relevant instruments for the trade_symbol"""
    global spot_instrument_tokens, nearest_expiry_dates
    try:
        # Read the CSV file
        df = pd.read_csv("kite_instruments.csv")
        
        print(f"📊 Total instruments in CSV: {len(df)}")
        
        # Find spot price instrument first
        if trade_symbol == "NIFTY":
            spot_df = df[
                (df['name'] == 'NIFTY 50') & 
                (df['segment'] == 'INDICES')
            ]
        elif trade_symbol == "SENSEX":
            spot_df = df[
                (df['name'] == 'SENSEX') & 
                (df['segment'] == 'INDICES')
            ]
        
        if not spot_df.empty:
            spot_instrument_tokens[trade_symbol] = int(spot_df.iloc[0]['instrument_token'])  # Convert to regular int
            spot_symbol = spot_df.iloc[0]['tradingsymbol']
            print(f"✅ Found spot instrument: {spot_symbol} (Token: {spot_instrument_tokens[trade_symbol]})")
        else:
            print(f"⚠️ No spot instrument found for {trade_symbol}")
            spot_instrument_tokens[trade_symbol] = None
        
        # Filter based on trade_symbol for options
        if trade_symbol == "NIFTY":
            # Filter for NIFTY options in NFO-OPT segment
            filtered_df = df[
                (df['name'] == 'NIFTY') & 
                (df['segment'] == 'NFO-OPT')
            ]
        elif trade_symbol == "SENSEX":
            # Filter for SENSEX options in BFO-OPT segment
            filtered_df = df[
                (df['name'] == 'SENSEX') & 
                (df['segment'] == 'BFO-OPT')
            ]
        else:
            print(f"❌ Unsupported trade_symbol: {trade_symbol}")
            return []
        
        print(f"📊 Filtered instruments for {trade_symbol}: {len(filtered_df)}")
        
        # Handle expiry date conversion with error handling
        # First, let's see what values are in the expiry column
        print(f"📊 Sample expiry values: {filtered_df['expiry'].head(10).tolist()}")
        
        # Filter out rows with invalid expiry dates
        # Convert expiry column to datetime with errors='coerce' to handle invalid dates
        filtered_df = filtered_df.copy()  # Create a copy to avoid SettingWithCopyWarning
        filtered_df['expiry'] = pd.to_datetime(filtered_df['expiry'], errors='coerce')
        
        # Remove rows where expiry conversion failed (NaN values)
        filtered_df = filtered_df.dropna(subset=['expiry'])
        
        print(f"📊 Valid instruments after expiry filtering: {len(filtered_df)}")
        
        if len(filtered_df) == 0:
            print("❌ No valid instruments found after expiry filtering")
            return []
        
        # Find the nearest expiry date
        today = datetime.now().date()
        # Calculate days to expiry properly using timedelta
        filtered_df['days_to_expiry'] = (filtered_df['expiry'].dt.date - today).apply(lambda x: x.days)
        nearest_expiry = filtered_df[filtered_df['days_to_expiry'] >= 0]['expiry'].min()
        
        if pd.isna(nearest_expiry):
            print("❌ No valid expiry dates found")
            return []
        
        nearest_expiry_dates[trade_symbol] = nearest_expiry # Update global variable
        
        # Filter for the nearest expiry
        nearest_instruments = filtered_df[filtered_df['expiry'] == nearest_expiry]
        
        print(f"✅ Found {len(nearest_instruments)} instruments for {trade_symbol} with expiry {nearest_expiry.strftime('%Y-%m-%d')}")
        
        # Create mapping of instrument_token to tradingsymbol
        instruments = []
        for _, row in nearest_instruments.iterrows():
            instruments.append({
                'instrument_token': int(row['instrument_token']),  # Convert to regular int
                'tradingsymbol': row['tradingsymbol'],
                'strike': row['strike'],
                'instrument_type': row['instrument_type'],
                'expiry': row['expiry'].strftime('%Y-%m-%d')
            })
            kite_instrument_mapping[int(row['instrument_token'])] = row['tradingsymbol']  # Convert to regular int
            # Store instrument details for database population
            kite_instrument_details[row['tradingsymbol']] = {
                'strike': row['strike'],
                'option_type': row['instrument_type'],
                # Ensure we store the actual expiry per tradingsymbol for accurate DB writes
                'expiry': row['expiry'].date(),
                'trade_symbol': trade_symbol
            }
        
        return instruments
        
    except Exception as e:
        print(f"❌ Error parsing kite_instruments.csv: {e}")
        return []

def parse_kite_instruments_multi(trade_symbols):
    """Parse kite_instruments.csv and return relevant instruments for multiple trade_symbols"""
    global spot_instrument_tokens, nearest_expiry_dates
    all_instruments = []
    
    try:
        # Read the CSV file
        df = pd.read_csv("kite_instruments.csv")
        
        print(f"📊 Total instruments in CSV: {len(df)}")
        
        for trade_symbol in trade_symbols:
            print(f"🔍 Processing {trade_symbol}...")
            
            # Find spot price instrument first
            if trade_symbol == "NIFTY":
                spot_df = df[
                    (df['name'] == 'NIFTY 50') & 
                    (df['segment'] == 'INDICES')
                ]
            elif trade_symbol == "SENSEX":
                spot_df = df[
                    (df['name'] == 'SENSEX') & 
                    (df['segment'] == 'INDICES')
                ]
            
            if not spot_df.empty:
                spot_instrument_tokens[trade_symbol] = int(spot_df.iloc[0]['instrument_token'])  # Convert to regular int
                spot_symbol = spot_df.iloc[0]['tradingsymbol']
                print(f"✅ Found spot instrument: {spot_symbol} (Token: {spot_instrument_tokens[trade_symbol]})")
            else:
                print(f"⚠️ No spot instrument found for {trade_symbol}")
                spot_instrument_tokens[trade_symbol] = None
            
            # Filter based on trade_symbol for options
            if trade_symbol == "NIFTY":
                # Filter for NIFTY options in NFO-OPT segment
                filtered_df = df[
                    (df['name'] == 'NIFTY') & 
                    (df['segment'] == 'NFO-OPT')
                ]
            elif trade_symbol == "SENSEX":
                # Filter for SENSEX options in BFO-OPT segment
                filtered_df = df[
                    (df['name'] == 'SENSEX') & 
                    (df['segment'] == 'BFO-OPT')
                ]
            else:
                print(f"❌ Unsupported trade_symbol: {trade_symbol}")
                continue
            
            print(f"📊 Filtered instruments for {trade_symbol}: {len(filtered_df)}")
            
            # Handle expiry date conversion with error handling
            # Convert expiry column to datetime with errors='coerce' to handle invalid dates
            filtered_df = filtered_df.copy()  # Create a copy to avoid SettingWithCopyWarning
            filtered_df['expiry'] = pd.to_datetime(filtered_df['expiry'], errors='coerce')
            
            # Remove rows where expiry conversion failed (NaN values)
            filtered_df = filtered_df.dropna(subset=['expiry'])
            
            print(f"📊 Valid instruments after expiry filtering for {trade_symbol}: {len(filtered_df)}")
            
            if len(filtered_df) == 0:
                print(f"❌ No valid instruments found after expiry filtering for {trade_symbol}")
                continue
            
            # Find the nearest expiry date
            today = datetime.now().date()
            # Calculate days to expiry properly using timedelta
            filtered_df['days_to_expiry'] = (filtered_df['expiry'].dt.date - today).apply(lambda x: x.days)
            nearest_expiry = filtered_df[filtered_df['days_to_expiry'] >= 0]['expiry'].min()
            
            if pd.isna(nearest_expiry):
                print(f"❌ No valid expiry dates found for {trade_symbol}")
                continue
            
            nearest_expiry_dates[trade_symbol] = nearest_expiry # Update global variable
            
            # Filter for the nearest expiry
            nearest_instruments = filtered_df[filtered_df['expiry'] == nearest_expiry]
            
            print(f"✅ Found {len(nearest_instruments)} instruments for {trade_symbol} with expiry {nearest_expiry.strftime('%Y-%m-%d')}")
            
            # Create mapping of instrument_token to tradingsymbol
            for _, row in nearest_instruments.iterrows():
                instrument = {
                    'instrument_token': int(row['instrument_token']),  # Convert to regular int
                    'tradingsymbol': row['tradingsymbol'],
                    'strike': row['strike'],
                    'instrument_type': row['instrument_type'],
                    'expiry': row['expiry'].strftime('%Y-%m-%d'),
                    'trade_symbol': trade_symbol  # Add trade_symbol to identify which symbol this belongs to
                }
                all_instruments.append(instrument)
                kite_instrument_mapping[int(row['instrument_token'])] = row['tradingsymbol']  # Convert to regular int
                # Store instrument details for database population
                kite_instrument_details[row['tradingsymbol']] = {
                    'strike': row['strike'],
                    'option_type': row['instrument_type'],
                    'trade_symbol': trade_symbol,  # Add trade_symbol to details
                    'expiry': row['expiry'].date(),
                }
        
        return all_instruments
        
    except Exception as e:
        print(f"❌ Error parsing kite_instruments.csv: {e}")
        return []

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("PGHOST", "localhost"),
            port=os.getenv("PGPORT", "5432"),
            dbname=os.getenv("PGDATABASE", "database_name"),
            user=os.getenv("PGUSER", "username"),
            password=os.getenv("PGPASSWORD", "password"),
            cursor_factory=RealDictCursor
        )
        logging.debug(f"Created new connection: {conn}")
        return conn
    except Exception as e:
        logging.error(f"Failed to connect to database: {e}")
        raise

def create_price_table(table_name):
    db_params = get_db_connection_params()
    conn = psycopg2.connect(**db_params)
    conn.autocommit = True
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute(f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = '{table_name}'
        );
    """)
    
    table_exists = cursor.fetchone()[0]
    
    if table_exists:
        # Drop the existing table to recreate with new schema
        cursor.execute(f"DROP TABLE {table_name}")
        print(f"🗑️ Dropped existing table {table_name} to recreate with new schema")

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            symbol TEXT PRIMARY KEY,
            price REAL,
            timestamp TIMESTAMP,
            trade_symbol TEXT,
            strike_price REAL,
            option_type TEXT,
            source TEXT,
            zerodha_price REAL,
            zerodha_timestamp TIMESTAMP,
            instrument_token INTEGER,
            expiry_date DATE
        )
    """)

    cursor.close()
    conn.close()
    print(f"✅ Created/verified table {table_name}")

def upsert_price(kite_symbol, price=None, trade_symbol=None, strike_price=None, option_type=None, source="Unknown", conn=None, kite_instrument_token=None, table_name=None, exchange_timestamp=None):
    db_start_time = datetime.now()
    
    # Use exchange timestamp if available, otherwise generate current timestamp
    if exchange_timestamp:
        # Convert datetime object to string format
        timestamp = exchange_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    else:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    
    # Prefer exact expiry mapped to this tradingsymbol if available; fall back to nearest_expiry for the index
    symbol_expiry = None
    try:
        details = kite_instrument_details.get(kite_symbol, {})
        symbol_expiry = details.get('expiry')
    except Exception:
        symbol_expiry = None

    expiry_date = symbol_expiry or nearest_expiry_dates.get(trade_symbol)
    close_conn = False
    if conn is None:
        db_params = get_db_connection_params()
        conn = psycopg2.connect(**db_params)
        close_conn = True

    try:
        with db_lock:
            cursor = conn.cursor()

            # Update source-specific columns (only price-related fields)
            if source.lower() == "zerodha":
                cursor.execute(f"""
                    INSERT INTO {table_name} (
                        symbol, zerodha_price, zerodha_timestamp, 
                        instrument_token, expiry_date
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE SET
                        zerodha_price = EXCLUDED.zerodha_price,
                        zerodha_timestamp = EXCLUDED.zerodha_timestamp,
                        instrument_token = EXCLUDED.instrument_token,
                        expiry_date = EXCLUDED.expiry_date
                """, (kite_symbol, price, timestamp, kite_instrument_token, expiry_date))
            else:
                # For unknown sources, update only the common columns
                cursor.execute(f"""
                    INSERT INTO {table_name} (
                        symbol, price, timestamp, 
                        instrument_token, expiry_date
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE SET
                        price = EXCLUDED.price,
                        timestamp = EXCLUDED.timestamp,
                        instrument_token = EXCLUDED.instrument_token,
                        expiry_date = EXCLUDED.expiry_date
                """, (kite_symbol, price, timestamp, kite_instrument_token, expiry_date))

            # Update price and timestamp based on the most recent source
            cursor.execute(f"""
                UPDATE {table_name}
                SET price = zerodha_price,
                    timestamp = zerodha_timestamp
                WHERE symbol = %s
                AND zerodha_price IS NOT NULL
            """, (kite_symbol,))

            conn.commit()
            cursor.close()
            
            db_end_time = datetime.now()
            db_time = (db_end_time - db_start_time).total_seconds() * 1000  # Convert to milliseconds
            print(f"💾 [DB] Updated {kite_symbol} in {db_time:.2f}ms")
            
    except Exception as e:
        logging.error(f"Error in upsert_price for {kite_symbol}: {e}")
        conn.rollback()
        raise
    finally:
        if close_conn and not conn.closed:
            conn.close()

def upsert_price_bulk(kite_symbols, prices, exchange_timestamps, source="Unknown", conn=None, table_name=None):
    """Bulk update prices for multiple instruments at once"""
    if not kite_symbols:
        return
        
    db_start_time = datetime.now()
    
    # Use exchange timestamp if available, otherwise generate current timestamp
    timestamps = []
    for exchange_timestamp in exchange_timestamps:
        if exchange_timestamp:
            timestamps.append(exchange_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        else:
            timestamps.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
    
    # Prepare per-symbol expiry dates; prefer exact expiry if available
    per_symbol_expiries = []
    for sym in kite_symbols:
        details = kite_instrument_details.get(sym, {})
        sym_expiry = details.get('expiry')
        trade_symbol = details.get('trade_symbol')
        per_symbol_expiries.append(sym_expiry or nearest_expiry_dates.get(trade_symbol))
    
    close_conn = False
    if conn is None:
        db_params = get_db_connection_params()
        conn = psycopg2.connect(**db_params)
        close_conn = True

    try:
        with db_lock:
            cursor = conn.cursor()
            
            # Bulk insert/update for all instruments
            if source.lower() == "zerodha":
                # Prepare bulk data with correct expiry per symbol
                bulk_data = []
                for i, kite_symbol in enumerate(kite_symbols):
                    bulk_data.append((kite_symbol, prices[i], timestamps[i], per_symbol_expiries[i]))
                
                # Execute bulk update
                cursor.executemany(f"""
                    INSERT INTO {table_name} (
                        symbol, zerodha_price, zerodha_timestamp, expiry_date
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE SET
                        zerodha_price = EXCLUDED.zerodha_price,
                        zerodha_timestamp = EXCLUDED.zerodha_timestamp,
                        expiry_date = EXCLUDED.expiry_date
                """, bulk_data)
                
                # Also update the main price column for all updated instruments
                cursor.executemany(f"""
                    UPDATE {table_name}
                    SET price = zerodha_price,
                        timestamp = zerodha_timestamp
                    WHERE symbol = %s
                    AND zerodha_price IS NOT NULL
                """, [(kite_symbol,) for kite_symbol in kite_symbols])
            
            conn.commit()
            cursor.close()
            
            db_end_time = datetime.now()
            db_time = (db_end_time - db_start_time).total_seconds() * 1000
            print(f"💾 [DB Bulk] Updated {len(kite_symbols)} instruments in {db_time:.2f}ms")
            
    except Exception as e:
        logging.error(f"Error in bulk upsert: {e}")
        conn.rollback()
        raise
    finally:
        if close_conn and not conn.closed:
            conn.close()

def upsert_spot_price(spot_symbol, price, trade_symbol, source="Unknown", conn=None, table_name=None, exchange_timestamp=None):
    """Update spot price in the database"""
    db_start_time = datetime.now()
    
    # Use exchange timestamp if available, otherwise generate current timestamp
    if exchange_timestamp:
        # Convert datetime object to string format
        timestamp = exchange_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    else:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    
    # Spot rows can safely use the nearest expiry for the corresponding index
    expiry_date = nearest_expiry_dates.get(trade_symbol)
    close_conn = False
    if conn is None:
        db_params = get_db_connection_params()
        conn = psycopg2.connect(**db_params)
        close_conn = True

    try:
        with db_lock:
            cursor = conn.cursor()

            # Update spot price
            cursor.execute(f"""
                INSERT INTO {table_name} (
                    symbol, zerodha_price, zerodha_timestamp, 
                    trade_symbol, source, expiry_date
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    zerodha_price = EXCLUDED.zerodha_price,
                    zerodha_timestamp = EXCLUDED.zerodha_timestamp,
                    trade_symbol = EXCLUDED.trade_symbol,
                    source = EXCLUDED.source,
                    expiry_date = EXCLUDED.expiry_date
            """, (spot_symbol, price, timestamp, trade_symbol, source, expiry_date))

            # Update price and timestamp based on the most recent source
            cursor.execute(f"""
                UPDATE {table_name}
                SET price = zerodha_price,
                    timestamp = zerodha_timestamp
                WHERE symbol = %s
                AND zerodha_price IS NOT NULL
            """, (spot_symbol,))

            conn.commit()
            cursor.close()
            
            db_end_time = datetime.now()
            db_time = (db_end_time - db_start_time).total_seconds() * 1000  # Convert to milliseconds
            print(f"💾 [DB] Updated spot {spot_symbol} in {db_time:.2f}ms")
            
    except Exception as e:
        logging.error(f"Error in upsert_spot_price for {spot_symbol}: {e}")
        conn.rollback()
        raise
    finally:
        if close_conn and not conn.closed:
            conn.close()

def populate_initial_instruments(table_name, trade_symbol, conn=None):
    """Populate the database with initial instrument data from Kite instruments"""
    close_conn = False
    if conn is None:
        db_params = get_db_connection_params()
        conn = psycopg2.connect(**db_params)
        close_conn = True
    
    try:
        with db_lock:
            cursor = conn.cursor()
            expiry_date = nearest_expiry_dates[trade_symbol] # Use global variable
            
            print(f"🔍 Debug: kite_instrument_details has {len(kite_instrument_details)} entries")
            print(f"🔍 Debug: kite_instrument_mapping has {len(kite_instrument_mapping)} entries")
            
            populated_count = 0
            for kite_symbol, details in kite_instrument_details.items():
                # Only populate instruments for the current trade_symbol
                if details.get('trade_symbol') != trade_symbol:
                    continue
                
                instrument_token = None
                for token, symbol in kite_instrument_mapping.items():
                    if symbol == kite_symbol:
                        instrument_token = token
                        break
                
                if not instrument_token:
                    continue
                
                # Get strike and option_type from details mapping
                strike = details['strike']
                option_type = details['option_type']
                print(f"🔍 Debug: {kite_symbol} -> Strike: {strike}, Type: {option_type}")
                
                # Insert initial record with basic info
                cursor.execute(f"""
                    INSERT INTO {table_name} (
                        symbol, trade_symbol, strike_price, option_type,
                        instrument_token, source, expiry_date
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE SET
                        trade_symbol = EXCLUDED.trade_symbol,
                        strike_price = EXCLUDED.strike_price,
                        option_type = EXCLUDED.option_type,
                        instrument_token = EXCLUDED.instrument_token,
                        expiry_date = EXCLUDED.expiry_date
                """, (kite_symbol, trade_symbol, strike, option_type, 
                      instrument_token, "Initial", expiry_date))
                
                populated_count += 1
            
            conn.commit()
            cursor.close()
            print(f"✅ Populated {populated_count} initial instrument records for {trade_symbol}")
            
    except Exception as e:
        logging.error(f"Error in populate_initial_instruments: {e}")
        conn.rollback()
        raise
    finally:
        if close_conn and not conn.closed:
            conn.close()

def get_atm_strike(price, step=50):
    return int(round(price / step) * step)

def get_index_price_and_symbol(table_name):
    """Get the current index price and symbol from the database"""
    with db_lock:
        db_params = get_db_connection_params()
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        index_symbol = None
        index_price = None

        # Check for NIFTY 50 and SENSEX in the database
        for candidate in ["NIFTY 50", "SENSEX"]:
            cursor.execute(f"SELECT price FROM {table_name} WHERE symbol = %s", (candidate,))
            row = cursor.fetchone()
            if row and row[0] is not None:
                index_symbol = candidate
                index_price = row[0]
                break

        cursor.close()
        conn.close()
        
        if index_symbol is None or index_price is None:
            return None, None
        return index_symbol, index_price

def database_worker(table_name, trade_symbols):
    conn = None
    batch_size = 50  # Increased batch size to process more per cycle
    batch_timeout = 0.1  # Faster timeout to process more frequently
    
    # Convert single trade_symbol to list if needed
    if isinstance(trade_symbols, str):
        trade_symbols = [trade_symbols]
    
    # Adaptive timeout based on queue size
    def get_adaptive_timeout():
        queue_size = tick_queue.qsize()
        if queue_size > 1000:
            return 0.05  # Very fast timeout for large queues
        elif queue_size > 500:
            return 0.1   # Fast timeout for medium queues
        elif queue_size > 200:
            return 0.2   # Medium timeout
        else:
            return 0.3   # Normal timeout for small queues
    
    # Adaptive batch sizing - more aggressive for smaller queue targets
    def get_adaptive_batch_size():
        import psutil
        cpu_percent = psutil.cpu_percent()
        queue_size = tick_queue.qsize()
        
        # If queue is very large, use larger batches regardless of CPU
        if queue_size > 2000:
            return 150  # Very large batches to catch up quickly
        elif queue_size > 1000:
            return 100  # Large batches to reduce queue
        elif queue_size > 500:
            return 75   # Medium-large batches
        elif queue_size > 200:
            return 50   # Medium batches
        elif queue_size > 100:
            return 35   # Smaller batches for fine control
        
        # Normal adaptive sizing based on CPU for small queues
        if cpu_percent > 80:
            return 25  # Smaller batches under high CPU load
        elif cpu_percent > 60:
            return 35  # Medium batches under moderate load
        else:
            return 50  # Normal batch size under low load

    while not shutdown_event.is_set():
        try:
            if conn is None or conn.closed:
                conn = get_db_connection()

            # Emergency processing for very large queues
            queue_size = tick_queue.qsize()
            if queue_size > 2000:  # Reduced from 3000 to trigger earlier
                print(f"🚨 [EMERGENCY] Queue size: {queue_size} - Processing all available ticks immediately!")
                # Process all available ticks in emergency mode
                emergency_batch = []
                try:
                    while not tick_queue.empty() and len(emergency_batch) < 300:  # Increased from 200 to process more
                        try:
                            tick = tick_queue.get_nowait()  # Non-blocking
                            emergency_batch.append(tick)
                            tick_queue.task_done()
                        except queue.Empty:
                            break
                    
                    if emergency_batch:
                        print(f"🚨 [EMERGENCY] Processing {len(emergency_batch)} ticks immediately")
                        # Process emergency batch with minimal logging
                        zerodha_ticks = []
                        spot_ticks = []
                        
                        for tick in emergency_batch:
                            source = tick['source']
                            data = tick['data']
                            
                            if source == 'zerodha':
                                instrument_token = data.get("instrument_token")
                                ltp = data.get("last_price")
                                exchange_timestamp = data.get("exchange_timestamp")
                                
                                if not instrument_token or ltp is None:
                                    continue
                                
                                # Check if this is a spot price tick for any trade symbol
                                spot_found = False
                                for trade_symbol in trade_symbols:
                                    if instrument_token == spot_instrument_tokens.get(trade_symbol):
                                        spot_symbol = "NIFTY 50" if trade_symbol == "NIFTY" else "SENSEX"
                                        spot_ticks.append({
                                            'spot_symbol': spot_symbol,
                                            'price': ltp,
                                            'exchange_timestamp': exchange_timestamp,
                                            'trade_symbol': trade_symbol
                                        })
                                        spot_found = True
                                        break
                                
                                # If not a spot tick, check if it's an option tick
                                if not spot_found:
                                    kite_symbol = kite_instrument_mapping.get(instrument_token)
                                    if kite_symbol:
                                        zerodha_ticks.append({
                                            'kite_symbol': kite_symbol,
                                            'price': ltp,
                                            'instrument_token': instrument_token,
                                            'exchange_timestamp': exchange_timestamp
                                        })
                        
                        # Process emergency batch
                        if spot_ticks:
                            for spot_tick in spot_ticks:
                                try:
                                    upsert_spot_price(
                                        spot_symbol=spot_tick['spot_symbol'],
                                        price=spot_tick['price'],
                                        trade_symbol=spot_tick['trade_symbol'],
                                        source='zerodha',
                                        conn=conn,
                                        table_name=table_name,
                                        exchange_timestamp=spot_tick['exchange_timestamp']
                                    )
                                except Exception as e:
                                    logging.error(f"Emergency spot update error: {e}")
                        
                        if zerodha_ticks:
                            try:
                                kite_symbols = [tick['kite_symbol'] for tick in zerodha_ticks]
                                prices = [tick['price'] for tick in zerodha_ticks]
                                exchange_timestamps = [tick['exchange_timestamp'] for tick in zerodha_ticks]
                                
                                upsert_price_bulk(
                                    kite_symbols=kite_symbols,
                                    prices=prices,
                                    exchange_timestamps=exchange_timestamps,
                                    source='zerodha',
                                    conn=conn,
                                    table_name=table_name
                                )
                                print(f"🚨 [EMERGENCY] Processed {len(zerodha_ticks)} ticks in emergency mode")
                            except Exception as e:
                                logging.error(f"Emergency bulk update error: {e}")
                                conn.rollback()
                        
                        conn.commit()
                        continue  # Skip normal processing and go back to emergency mode
                        
                except Exception as e:
                    logging.error(f"Emergency processing error: {e}")
                    if conn and not conn.closed:
                        conn.rollback()

            # Collect batch of ticks
            batch = []
            batch_start_time = datetime.now()
            current_batch_size = get_adaptive_batch_size()  # Get adaptive batch size
            try:
                while len(batch) < current_batch_size and not shutdown_event.is_set():
                    try:
                        tick = tick_queue.get(timeout=get_adaptive_timeout())  # Use adaptive timeout
                        batch.append(tick)
                        tick_queue.task_done()
                        
                        # Calculate queue staleness
                        queue_entry_time = tick.get('queue_entry_time')
                        current_time = datetime.now()
                        if queue_entry_time:
                            queue_delay = (current_time - queue_entry_time).total_seconds()
                            print(f"📤 [Queue] Retrieved tick at {current_time.strftime('%H:%M:%S.%f')[:-3]} | Queue delay: {queue_delay:.2f}s")
                        else:
                            print(f"📤 [Queue] Retrieved tick at {current_time.strftime('%H:%M:%S.%f')[:-3]} | No queue timestamp")
                            
                    except queue.Empty:
                        break
            except Exception as e:
                logging.error(f"Error fetching from tick queue: {e}")
                continue

            if not batch:
                continue

            print(f"🔄 [DB Worker] Processing {len(batch)} ticks at {datetime.now().strftime('%H:%M:%S.%f')[:-3]} | Queue size: {tick_queue.qsize()}")

            # Process batch using bulk updates for better performance
            zerodha_ticks = []
            spot_ticks = []
            
            for tick in batch:
                try:
                    source = tick['source']
                    data = tick['data']
                    
                    if source == 'zerodha':
                        instrument_token = data.get("instrument_token")
                        ltp = data.get("last_price")
                        exchange_timestamp = data.get("exchange_timestamp")
                        
                        print(f"💾 [DB Worker] Processing tick for instrument {instrument_token}, price {ltp}, exchange_time {exchange_timestamp}")
                        
                        # Calculate delay between exchange time and processing time
                        if exchange_timestamp:
                            current_time = datetime.now()
                            delay_seconds = (current_time - exchange_timestamp).total_seconds()
                            
                            # Update delay statistics
                            delay_stats['count'] += 1
                            delay_stats['total_delay'] += delay_seconds
                            delay_stats['min_delay'] = min(delay_stats['min_delay'], delay_seconds)
                            delay_stats['max_delay'] = max(delay_stats['max_delay'], delay_seconds)
                            
                            avg_delay = delay_stats['total_delay'] / delay_stats['count']
                            # Only log delay every 10 ticks to reduce overhead
                            if delay_stats['count'] % 10 == 0:
                                print(f"⏱️ [Delay] Exchange: {exchange_timestamp.strftime('%H:%M:%S')} | Processing: {current_time.strftime('%H:%M:%S')} | Delay: {delay_seconds:.1f}s | Avg: {avg_delay:.1f}s | Min: {delay_stats['min_delay']:.1f}s | Max: {delay_stats['max_delay']:.1f}s")
                        
                        if not instrument_token or ltp is None:
                            logging.debug(f"Skipping Zerodha tick: missing instrument_token or last_price - {data}")
                            continue
                        
                        # Check if this is a spot price tick
                        spot_found = False
                        for trade_symbol in trade_symbols:
                            if instrument_token == spot_instrument_tokens.get(trade_symbol):
                                spot_symbol = "NIFTY 50" if trade_symbol == "NIFTY" else "SENSEX"
                                spot_ticks.append({
                                    'spot_symbol': spot_symbol,
                                    'price': ltp,
                                    'exchange_timestamp': exchange_timestamp,
                                    'trade_symbol': trade_symbol
                                })
                                spot_found = True
                                break
                        
                        # If not a spot tick, check if it's an option tick
                        if not spot_found:
                            kite_symbol = kite_instrument_mapping.get(instrument_token)
                            if not kite_symbol:
                                logging.debug(f"No kite_symbol found for instrument_token {instrument_token}")
                                continue
                            
                            zerodha_ticks.append({
                                'kite_symbol': kite_symbol,
                                'price': ltp,
                                'instrument_token': instrument_token,
                                'exchange_timestamp': exchange_timestamp
                            })

                except Exception as e:
                    logging.error(f"Error processing tick from {source} for {data.get('symbol', data.get('instrument_token', 'unknown'))}: {e}")
                    continue

            # Process spot prices individually (usually only 1 per batch)
            for spot_tick in spot_ticks:
                try:
                    print(f"📈 [DB Worker] Updating spot price for {spot_tick['spot_symbol']}")
                    upsert_spot_price(
                        spot_symbol=spot_tick['spot_symbol'],
                        price=spot_tick['price'],
                        trade_symbol=spot_tick['trade_symbol'],
                        source='zerodha',
                        conn=conn,
                        table_name=table_name,
                        exchange_timestamp=spot_tick['exchange_timestamp']
                    )
                except Exception as e:
                    logging.error(f"Error updating spot price: {e}")
                    conn.rollback()

            # Process option prices in bulk for better performance
            if zerodha_ticks:
                try:
                    kite_symbols = [tick['kite_symbol'] for tick in zerodha_ticks]
                    prices = [tick['price'] for tick in zerodha_ticks]
                    exchange_timestamps = [tick['exchange_timestamp'] for tick in zerodha_ticks]
                    
                    print(f"📈 [DB Worker] Bulk updating {len(zerodha_ticks)} option prices")
                    upsert_price_bulk(
                        kite_symbols=kite_symbols,
                        prices=prices,
                        exchange_timestamps=exchange_timestamps,
                        source='zerodha',
                        conn=conn,
                        table_name=table_name
                    )
                except Exception as e:
                    logging.error(f"Error in bulk update: {e}")
                    conn.rollback()

            # Handle straddle price updates after processing all ticks
            for trade_symbol in trade_symbols:
                index_symbol, index_price = get_index_price_and_symbol(table_name)
                if index_price:
                    step = 50 if trade_symbol == "NIFTY" else 100
                    ATM_STRIKE = get_atm_strike(index_price, step=step)
                    
                    # Find CE and PE symbols for ATM strike for this trade symbol
                    ce_symbol = None
                    pe_symbol = None
                    
                    for kite_symbol, details in kite_instrument_details.items():
                        if details.get('trade_symbol') == trade_symbol and details['strike'] == ATM_STRIKE:
                            if details['option_type'] == 'CE':
                                ce_symbol = kite_symbol
                            elif details['option_type'] == 'PE':
                                pe_symbol = kite_symbol
                    
            conn.commit()
            batch_end_time = datetime.now()
            processing_time = (batch_end_time - batch_start_time).total_seconds() * 1000  # Convert to milliseconds
            print(f"✅ [DB Worker] Processed batch of {len(batch)} ticks in {processing_time:.2f}ms at {batch_end_time.strftime('%H:%M:%S.%f')[:-3]}")

        except Exception as e:
            logging.error(f"Error in database_worker: {e}", exc_info=True)
            if conn and not conn.closed:
                conn.rollback()
            if conn:
                conn.close()
                conn = None
            tm.sleep(1)

    if conn and not conn.closed:
        conn.close()

def zerodha_authenticate():
    """Authenticate with Zerodha using user_id, password, TOTP, api_key, and api_secret."""
    try:
        # Initialize session and login
        session = requests.Session()
        login_url = "https://kite.zerodha.com/api/login"
        twofa_url = "https://kite.zerodha.com/api/twofa"
        response = session.post(login_url, data={
            'user_id': creds['user_id'],
            'password': creds['password']
        })
        print(f"DEBUG: Zerodha login response status: {response.status_code}")
        if response.status_code != 200:
            raise Exception(f"Login failed: {response.text}")
        request_id = json.loads(response.text)['data']['request_id']
        print(f"DEBUG: Zerodha login success, request_id: {request_id}")

        # Verify TOTP
        twofa_pin = pyotp.TOTP(creds['totp_key']).now()
        response_1 = session.post(twofa_url, data={
            'user_id': creds['user_id'],
            'request_id': request_id,
            'twofa_value': twofa_pin,
            'twofa_type': 'totp'
        })
        print(f"DEBUG: Zerodha TOTP response status: {response_1.status_code}")
        if response_1.status_code != 200:
            raise Exception(f"TOTP verification failed: {response_1.text}")

        # Initialize KiteConnect and get request_token
        kite = KiteConnect(api_key=creds['api_key'])
        kite_url = kite.login_url()
        print(f"DEBUG: Zerodha Kite login URL: {kite_url}")
        try:
            session.get(kite_url)
        except Exception as e:
            e_msg = str(e)
            request_token = e_msg.split('request_token=')[1].split(' ')[0].split('&action')[0]
            print(f"DEBUG: Zerodha login successful, request_token: {request_token}")

        # Generate access_token
        access_token = kite.generate_session(request_token, creds['api_secret'])['access_token']
        kite.set_access_token(access_token)
        print(f"DEBUG: Zerodha authentication success, access_token: {access_token}")
        return kite, access_token
    except Exception as e:
        print(f"❌ Zerodha authentication failed: {e}")
        sys.exit()

def zerodha_on_ticks(ws, ticks):
    global last_activity_time
    try:
        last_activity_time = tm.time()  # Update activity time
        print(f"📊 [WebSocket] Received {len(ticks)} ticks at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        for tick in ticks:
            # Add queue entry time to track staleness
            tick_with_timestamp = {
                'source': 'zerodha', 
                'data': tick,
                'queue_entry_time': datetime.now()
            }
            tick_queue.put(tick_with_timestamp)
            # Only log queue size every 10 ticks to reduce overhead
            if tick_queue.qsize() % 10 == 0:
                print(f"📥 [Queue] Added tick for instrument {tick.get('instrument_token')} at {datetime.now().strftime('%H:%M:%S.%f')[:-3]} | Queue size: {tick_queue.qsize()}")
    except Exception as e:
        logging.error(f"Error in zerodha_on_ticks: {e}", exc_info=True)

def zerodha_on_connect(ws, response):
    global zerodha_connected
    zerodha_connected = True
    
    # Get all instrument tokens including spot for all trade symbols
    instrument_tokens = list(kite_instrument_mapping.keys())
    
    # Add spot instrument tokens if available
    for trade_symbol in spot_instrument_tokens.keys():
        if spot_instrument_tokens[trade_symbol]:
            instrument_tokens.append(spot_instrument_tokens[trade_symbol])
    
    print(f"✅ [Zerodha] Connected, subscribing to {len(instrument_tokens)} instrument tokens (including spot for all symbols)")
    
    try:
        print(f"✅ [Zerodha] Successfully subscribed to {len(instrument_tokens)} instruments")
        ws.subscribe(instrument_tokens)
        ws.set_mode(ws.MODE_FULL, instrument_tokens)
        print(f"✅ [Zerodha] Successfully subscribed to {len(instrument_tokens)} instruments")
    except Exception as e:
        print(f"❌ [Zerodha] Error subscribing to instruments: {e}")
        zerodha_connected = False

def zerodha_on_error(ws, code, reason):
    global zerodha_connected, reconnect_attempts
    print(f"❌ [Zerodha] Error: code={code}, reason={reason}")
    zerodha_connected = False
    
    # Don't reconnect for certain error codes
    if code in [1000, 1001]:  # Normal closure codes
        print("✅ [Zerodha] Normal connection closure")
        return
    
    if reconnect_attempts >= MAX_RECONNECTS:
        print("❌ [Zerodha] Max reconnection attempts reached. Stopping.")
        return
    
    reconnect_attempts += 1
    print(f"🔄 [Zerodha] Reconnection attempt {reconnect_attempts}/{MAX_RECONNECTS} in 5 seconds...")
    tm.sleep(5)  # Wait longer before reconnecting
    
    # Reset access token for reconnection
    global kite_access_token
    kite_access_token = None
    
    try:
        run_zerodha_websocket()
    except Exception as e:
        print(f"❌ [Zerodha] Reconnection failed: {e}")

def zerodha_on_close(ws, code, reason):
    global zerodha_connected
    print(f"❌ [Zerodha] Connection closed: {code}, {reason}")
    zerodha_connected = False

def read_config_from_txt(file_path="user_config.txt"):
    config = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    key_value = line.split('=', 1)
                    if len(key_value) == 2:
                        key, value = key_value
                        config[key.strip()] = value.strip()
    except FileNotFoundError:
        print("⚠️ Config file not found. Proceeding with empty config.")
    return config

def run_zerodha_websocket():
    global kite_access_token, reconnect_attempts
    try:
        if kite_access_token is None:
            print("❌ [Zerodha] No access token available. Re-authenticating...")
            kite, kite_access_token = zerodha_authenticate()
        
        kws = KiteTicker(creds['api_key'], kite_access_token)
    except Exception as e:
        print(f"❌ [Zerodha] Token invalid: {e}. Re-authenticating...")
        kite, kite_access_token = zerodha_authenticate()
        kws = KiteTicker(creds['api_key'], kite_access_token)
    
    kws.on_ticks = zerodha_on_ticks
    kws.on_connect = zerodha_on_connect
    kws.on_error = zerodha_on_error
    kws.on_close = zerodha_on_close
    
    try:
        print("🔄 [Zerodha] Attempting to connect...")
        kws.connect()
        print("✅ [Zerodha] WebSocket connection initiated")
        
        # Keep the connection alive with better monitoring
        connection_start_time = tm.time()
        
        while not shutdown_event.is_set():
            tm.sleep(1)
            
            # Check if connection is still alive
            if not kws.is_connected():
                print("⚠️ [Zerodha] Connection lost, attempting to reconnect...")
                break
            
            # Check for connection timeout (5 minutes without activity)
            current_time = tm.time()
            if current_time - last_activity_time > 300:  # 5 minutes
                print("⚠️ [Zerodha] Connection timeout, reconnecting...")
                break
                
    except Exception as e:
        print(f"❌ [Zerodha] WebSocket error: {e}")
    finally:
        try:
            kws.close()
        except:
            pass

def monitor_queue_health():
    """Monitor queue health and alert if queue gets too large"""
    while not shutdown_event.is_set():
        try:
            queue_size = tick_queue.qsize()
            if queue_size > 100:
                print(f"⚠️ [Queue Alert] Queue size: {queue_size} - Processing may be falling behind!")
            if queue_size > 500:
                print(f"🚨 [Queue Critical] Queue size: {queue_size} - Significant backlog detected!")
            if queue_size > 1000:
                print(f"💥 [Queue Emergency] Queue size: {queue_size} - Critical backlog! Consider reducing batch size or adding workers!")
            tm.sleep(5)  # Check every 5 seconds
        except Exception as e:
            logging.error(f"Error in queue monitoring: {e}")
            tm.sleep(5)

def monitor_system_health():
    """Monitor system health including CPU usage and queue size"""
    import psutil
    while not shutdown_event.is_set():
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            queue_size = tick_queue.qsize()
            
            print(f"📊 [System] CPU: {cpu_percent:.1f}% | Memory: {memory_percent:.1f}% | Queue: {queue_size}")
            
            # Alert if system is under stress
            if cpu_percent > 80:
                print(f"⚠️ [CPU Alert] High CPU usage: {cpu_percent:.1f}% - Consider reducing batch size")
            if memory_percent > 80:
                print(f"⚠️ [Memory Alert] High memory usage: {memory_percent:.1f}%")
            if queue_size > 500:
                print(f"⚠️ [Queue Alert] Queue size: {queue_size} - Processing may be falling behind!")
            if queue_size > 1000:
                print(f"🚨 [Queue Critical] Queue size: {queue_size} - Significant backlog detected!")
            if queue_size > 2000:
                print(f"💥 [Queue Emergency] Queue size: {queue_size} - Critical backlog! Emergency mode should activate!")
            
            tm.sleep(10)  # Check every 10 seconds
        except Exception as e:
            logging.error(f"Error in system monitoring: {e}")
            tm.sleep(10)

def main():
    global kite_access_token, kite
    print("🚀 Starting Kite WebSocket with instruments from CSV...")
    
    # Read configuration
    config = read_config_from_txt()
    trade_symbols = config.get("trade_symbols", "NIFTY,SENSEX").split(",")
    trade_symbols = [symbol.strip() for symbol in trade_symbols if symbol.strip()]
    
    if not trade_symbols:
        print("❌ No trade_symbols found in config. Please set trade_symbols=NIFTY,SENSEX in user_config.txt")
        sys.exit(1)
    
    # Validate trade symbols
    valid_symbols = ["NIFTY", "SENSEX"]
    for symbol in trade_symbols:
        if symbol not in valid_symbols:
            print(f"❌ Unsupported trade_symbol: {symbol}. Please use NIFTY or SENSEX")
            sys.exit(1)
    
    print(f"📊 Using trade_symbols: {', '.join(trade_symbols)}")
    
    # Download and parse Kite instruments
    print("📥 Downloading Kite instruments...")
    if not download_kite_instruments():
        print("❌ Failed to download Kite instruments. Exiting.")
        sys.exit(1)
    
    print("📊 Parsing Kite instruments for multiple symbols...")
    kite_instruments = parse_kite_instruments_multi(trade_symbols)
    if not kite_instruments:
        print("❌ No instruments found. Exiting.")
        sys.exit(1)
    
    print(f"✅ Found {len(kite_instruments)} total instruments across all symbols")
    
    # Print instrument details by symbol
    for trade_symbol in trade_symbols:
        symbol_instruments = [inst for inst in kite_instruments if inst.get('trade_symbol') == trade_symbol]
        print(f"📊 {trade_symbol}: {len(symbol_instruments)} instruments")
        
        # Print first few instruments for each symbol
        for instrument in symbol_instruments[:3]:  # Show first 3 instruments
            kite_symbol = instrument['tradingsymbol']
            instrument_token = instrument['instrument_token']
            strike = instrument['strike']
            option_type = instrument['instrument_type']
            expiry = instrument['expiry']
            print(f"  → {kite_symbol} (Token: {instrument_token}, Strike: {strike}, Type: {option_type}, Expiry: {expiry})")
    
    # Create database table
    today_str = datetime.today().strftime('%Y%m%d')
    table_name = f"live_prices"
    create_price_table(table_name)
    
    # Populate initial instrument data for all symbols
    for trade_symbol in trade_symbols:
        populate_initial_instruments(table_name, trade_symbol)
    
    # Start database worker threads for each symbol
    num_workers = 6  # Increased from 4 to handle load more aggressively
    db_threads = []
    for i in range(num_workers):
        # Each worker will handle all symbols
        db_thread = threading.Thread(target=database_worker, args=(table_name, trade_symbols), daemon=True)
        db_thread.start()
        db_threads.append(db_thread)
        print(f"✅ Started database worker thread {i+1}")
    
    # Start queue monitoring thread
    queue_monitor_thread = threading.Thread(target=monitor_queue_health, daemon=True)
    queue_monitor_thread.start()
    print("✅ Started queue monitoring thread")

    # Start system health monitoring thread
    system_monitor_thread = threading.Thread(target=monitor_system_health, daemon=True)
    system_monitor_thread.start()
    print("✅ Started system health monitoring thread")
    
    # Authenticate Zerodha
    print("🔐 Authenticating with Zerodha...")
    kite, kite_access_token = zerodha_authenticate()
    
    # Run Zerodha WebSocket in main thread
    try:
        while not shutdown_event.is_set():
            try:
                run_zerodha_websocket()
                if shutdown_event.is_set():
                    break
                print("🔄 [Zerodha] Connection ended, restarting...")
                tm.sleep(2)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"❌ [Zerodha] WebSocket error: {e}")
                if not shutdown_event.is_set():
                    print("🔄 [Zerodha] Restarting WebSocket in 5 seconds...")
                    tm.sleep(5)
    except KeyboardInterrupt:
        print("Received Ctrl+C, shutting down...")
        shutdown_event.set()
        while not tick_queue.empty() and db_thread.is_alive():
            print(f"Waiting for {tick_queue.qsize()} remaining ticks to be processed...")
            tm.sleep(1)
        db_thread.join(timeout=5)
        print("Shutdown complete")
        sys.exit(0)

def start_websocket_service():
    """Start the WebSocket service for all configured symbols"""
    global websocket_running, websocket_thread, websocket_trade_symbols
    
    if websocket_running:
        return True
    
    try:
        # Read configuration
        config = read_config_from_txt()
        trade_symbols = config.get("trade_symbols", "NIFTY,SENSEX").split(",")
        trade_symbols = [symbol.strip() for symbol in trade_symbols if symbol.strip()]
        
        if not trade_symbols:
            print("❌ No trade_symbols found in config")
            return False
        
        websocket_trade_symbols = trade_symbols
        websocket_running = True
        
        # Start WebSocket in a separate thread
        websocket_thread = threading.Thread(target=run_websocket_main, args=(trade_symbols,), daemon=True)
        websocket_thread.start()
        
        print(f"✅ WebSocket service started for symbols: {', '.join(trade_symbols)}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to start WebSocket service: {e}")
        websocket_running = False
        return False

def stop_websocket_service():
    """Stop the WebSocket service"""
    global websocket_running, websocket_thread
    
    if not websocket_running:
        return True
    
    try:
        websocket_running = False
        shutdown_event.set()
        
        if websocket_thread and websocket_thread.is_alive():
            websocket_thread.join(timeout=10)
        
        print("✅ WebSocket service stopped")
        return True
        
    except Exception as e:
        print(f"❌ Failed to stop WebSocket service: {e}")
        return False

def get_websocket_status():
    """Get the current status of the WebSocket service"""
    global websocket_running, websocket_trade_symbols
    try:
        running = websocket_running and _is_market_hours_now()
        # Live diagnostics
        try:
            qsize = tick_queue.qsize()
        except Exception:
            qsize = 0
        return {
            'running': running,
            'is_running': running,  # alias for frontend compatibility
            'trade_symbols': websocket_trade_symbols if running else [],
            'available': True,
            'queue_size': qsize,
            'zerodha_connected': bool(zerodha_connected),
            'message': (
                'WebSocket running during market hours' if running else 'WebSocket closed (outside market hours)'
            )
        }
    except Exception:
        return {
            'running': False,
            'is_running': False,
            'trade_symbols': [],
            'available': True,
            'queue_size': 0,
            'zerodha_connected': False,
            'message': 'WebSocket status unavailable'
        }

def run_websocket_main(trade_symbols):
    """Main WebSocket function that runs in a separate thread"""
    global websocket_running
    
    try:
        print(f"🚀 Starting Kite WebSocket with instruments from CSV...")
        print(f"📊 Using trade_symbols: {', '.join(trade_symbols)}")
        
        # Download and parse Kite instruments
        print("📥 Downloading Kite instruments...")
        if not download_kite_instruments():
            print("❌ Failed to download Kite instruments. Exiting.")
            return
        
        print("📊 Parsing Kite instruments for multiple symbols...")
        kite_instruments = parse_kite_instruments_multi(trade_symbols)
        if not kite_instruments:
            print("❌ No instruments found. Exiting.")
            return
        
        print(f"✅ Found {len(kite_instruments)} total instruments across all symbols")
        
        # Create database table
        today_str = datetime.today().strftime('%Y%m%d')
        table_name = f"live_prices"
        create_price_table(table_name)
        
        # Populate initial instrument data for all symbols
        for trade_symbol in trade_symbols:
            populate_initial_instruments(table_name, trade_symbol)
        
        # Start database worker threads
        num_workers = 6
        db_threads = []
        for i in range(num_workers):
            db_thread = threading.Thread(target=database_worker, args=(table_name, trade_symbols), daemon=True)
            db_thread.start()
            db_threads.append(db_thread)
            print(f"✅ Started database worker thread {i+1}")
        
        # Start monitoring threads
        queue_monitor_thread = threading.Thread(target=monitor_queue_health, daemon=True)
        queue_monitor_thread.start()
        
        system_monitor_thread = threading.Thread(target=monitor_system_health, daemon=True)
        system_monitor_thread.start()
        
        # Authenticate Zerodha
        print("🔐 Authenticating with Zerodha...")
        kite, kite_access_token = zerodha_authenticate()
        
        # Run Zerodha WebSocket
        while websocket_running and not shutdown_event.is_set():
            try:
                run_zerodha_websocket()
                if not websocket_running or shutdown_event.is_set():
                    break
                print("🔄 [Zerodha] Connection ended, restarting...")
                tm.sleep(2)
            except Exception as e:
                print(f"❌ [Zerodha] WebSocket error: {e}")
                if not websocket_running or shutdown_event.is_set():
                    break
                print("🔄 [Zerodha] Restarting WebSocket in 5 seconds...")
                tm.sleep(5)
                
    except Exception as e:
        print(f"❌ Error in WebSocket main: {e}")
    finally:
        websocket_running = False
        print("🛑 WebSocket service stopped")

if __name__ == "__main__":
    main() 