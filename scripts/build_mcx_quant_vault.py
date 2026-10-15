import os
import sys
import time
from datetime import datetime, timedelta
import pandas as pd
import duckdb
from fyers_apiv3 import fyersModel

CLIENT_ID = "3WWLJD8YE4-200"
VAULT_DIR = "data/mcx_vault"
os.makedirs(VAULT_DIR, exist_ok=True)

with open("data/fyers_auth/access_token.txt") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=access_token, log_path="")

def download_continuous_series(symbol, start_year=2019, resolution="1", chunk_days=90):
    """
    Safely downloads full continuous history from start_year up to today.
    Enforces polite rate-limiting (0.5s sleep per request) to prevent any ban or throttling.
    """
    now = datetime.now()
    start_dt = datetime(start_year, 1, 1)
    
    print("\n" + "=" * 80)
    print(f"DOWNLOADING {symbol} (Resolution: {resolution}) FROM {start_year} TO {now.year}")
    print("=" * 80)
    
    chunks = []
    curr_end = now
    chunk_count = 0
    
    while curr_end > start_dt:
        curr_start = max(start_dt, curr_end - timedelta(days=chunk_days))
        payload = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "1",
            "range_from": curr_start.strftime("%Y-%m-%d"),
            "range_to": curr_end.strftime("%Y-%m-%d"),
            "cont_flag": "1",
            "oi_flag": "1"
        }
        
        success = False
        retries = 3
        while retries > 0 and not success:
            try:
                resp = fyers.history(data=payload)
                if resp.get("s") == "ok" and resp.get("candles"):
                    candles = resp["candles"]
                    cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
                    df_chunk = pd.DataFrame(candles, columns=cols[:len(candles[0])])
                    chunks.append(df_chunk)
                    chunk_count += 1
                    print(f"  [{chunk_count:02d}] {curr_start.strftime('%Y-%m-%d')} -> {curr_end.strftime('%Y-%m-%d')}: {len(df_chunk):,} candles")
                    success = True
                elif resp.get("message") == "No data found" or not resp.get("candles"):
                    print(f"  [{chunk_count:02d}] {curr_start.strftime('%Y-%m-%d')} -> {curr_end.strftime('%Y-%m-%d')}: No data / earliest boundary reached.")
                    success = True # Stop retrying if no data exists before this
                else:
                    print(f"  Warning on chunk ({resp.get('message', resp)}), retrying in 2s...")
                    time.sleep(2.0)
                    retries -= 1
            except Exception as e:
                print(f"  Exception {e}, retrying in 2s...")
                time.sleep(2.0)
                retries -= 1
        
        curr_end = curr_start - timedelta(days=1)
        time.sleep(0.4) # Polite 400ms sleep to stay 100% compliant with FYERS rate limits
    
    if not chunks:
        print(f"No data retrieved for {symbol}.")
        return None
    
    df = pd.concat(chunks, ignore_index=True)
    df = df.drop_duplicates(subset=["epoch"]).sort_values("epoch").reset_index(drop=True)
    df["ts_ist"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    
    # Clean symbol name for file naming
    clean_sym = symbol.split(":")[1].split("26")[0] # e.g. NATURALGAS or NATGASMINI
    res_label = f"{resolution}m" if resolution.isdigit() else resolution
    parquet_path = os.path.join(VAULT_DIR, f"{clean_sym}_{res_label}_continuous_2019_2026.parquet")
    
    df.to_parquet(parquet_path, compression="zstd")
    file_size_mb = os.path.getsize(parquet_path) / (1024 * 1024)
    
    print("-" * 80)
    print(f"COMPLETED {clean_sym} ({res_label}):")
    print(f"  Total Candles: {len(df):,}")
    print(f"  Span         : {df['ts_ist'].min()} -> {df['ts_ist'].max()}")
    print(f"  Storage Size : {file_size_mb:.2f} MB (ZSTD Compressed Parquet)")
    print(f"  Saved to     : {parquet_path}")
    print("-" * 80)
    
    return df

def build_duckdb_vault():
    """
    Indexes all parquet files into a unified high-performance DuckDB database.
    """
    db_path = os.path.join(VAULT_DIR, "mcx_quant.duckdb")
    con = duckdb.connect(db_path)
    
    print("\nRegistering datasets in unified DuckDB database...")
    for f in os.listdir(VAULT_DIR):
        if f.endswith(".parquet"):
            table_name = f.replace(".parquet", "")
            full_path = os.path.join(VAULT_DIR, f).replace("\\", "/")
            con.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{full_path}')")
            row_count = con.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
            print(f"  Created View: {table_name} ({row_count:,} rows)")
    
    con.close()
    print(f"DuckDB vault initialized successfully at {db_path}!")

if __name__ == "__main__":
    # 1. Download full 2019-2026 Natural Gas continuous 1-minute data
    download_continuous_series("MCX:NATURALGAS26OCTFUT", start_year=2019, resolution="1", chunk_days=90)
    
    # 2. Download Natural Gas Mini continuous 1-minute data (Mini contracts launched in 2023)
    download_continuous_series("MCX:NATGASMINI26OCTFUT", start_year=2023, resolution="1", chunk_days=90)
    
    # 3. Download Natural Gas continuous 5-minute data (2019-2026) for fast multi-year backtesting
    download_continuous_series("MCX:NATURALGAS26OCTFUT", start_year=2019, resolution="5", chunk_days=100)
    
    # 4. Build unified DuckDB database
    build_duckdb_vault()
