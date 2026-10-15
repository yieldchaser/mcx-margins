import os
import time
import pandas as pd
from datetime import datetime, timedelta
from fyers_apiv3 import fyersModel

CLIENT_ID = "3WWLJD8YE4-200"

with open("data/fyers_auth/access_token.txt") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=access_token, log_path="")

def fetch_continuous_multimonth(symbol, total_days=365):
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=total_days)
    
    chunks = []
    curr_end = end_dt
    
    print(f"\n=======================================================")
    print(f"DOWNLOADING {symbol} CONTINUOUS 1-MIN DATA ({total_days} DAYS)")
    print(f"=======================================================")
    
    while curr_end > start_dt:
        curr_start = max(start_dt, curr_end - timedelta(days=90))
        payload = {
            "symbol": symbol,
            "resolution": "1",
            "date_format": "1",
            "range_from": curr_start.strftime("%Y-%m-%d"),
            "range_to": curr_end.strftime("%Y-%m-%d"),
            "cont_flag": "1",
            "oi_flag": "1"
        }
        
        resp = fyers.history(data=payload)
        if resp.get("s") == "ok" and resp.get("candles"):
            candles = resp["candles"]
            cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
            df_chunk = pd.DataFrame(candles, columns=cols[:len(candles[0])])
            chunks.append(df_chunk)
            print(f"  Chunk {curr_start.strftime('%Y-%m-%d')} -> {curr_end.strftime('%Y-%m-%d')}: {len(df_chunk):,} candles")
        else:
            print(f"  Chunk {curr_start.strftime('%Y-%m-%d')} -> {curr_end.strftime('%Y-%m-%d')}: Response {resp.get('message', resp)}")
        
        curr_end = curr_start - timedelta(days=1)
        time.sleep(0.2) # Rate limit safety
    
    if chunks:
        df = pd.concat(chunks, ignore_index=True)
        df = df.drop_duplicates(subset=['epoch']).sort_values('epoch').reset_index(drop=True)
        df['ts_ist'] = pd.to_datetime(df['epoch'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
        save_file = f"data/fyers_{symbol.replace(':', '_')}_continuous_1m.csv"
        df.to_csv(save_file, index=False)
        print(f"--> COMPLETED: Saved {len(df):,} continuous 1-min candles to {save_file}")
        print(f"--> Span: {df['ts_ist'].min()} to {df['ts_ist'].max()}")
        return df
    return None

# Test 1: NATGASMINI
fetch_continuous_multimonth("MCX:NATGASMINI26OCTFUT", total_days=180)

# Test 2: Full Natural Gas 1-Year Continuous
fetch_continuous_multimonth("MCX:NATURALGAS26OCTFUT", total_days=365)
