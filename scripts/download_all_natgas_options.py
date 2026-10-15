import os
import time
from datetime import datetime, timedelta
import pandas as pd
import duckdb
from fyers_apiv3 import fyersModel

CLIENT_ID = "3WWLJD8YE4-200"
OPTIONS_DIR = "data/mcx_vault/options/natgas_oct26"
os.makedirs(OPTIONS_DIR, exist_ok=True)

with open("data/fyers_auth/access_token.txt") as f:
    token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=token, log_path="")

# 1. Load active strikes from our saved option chain
strikes_df = pd.read_parquet("data/mcx_vault/expanded/naturalgas_optionchain_strikes.parquet")
# Filter out the underlying futures symbol (strike_price == -1)
option_symbols = strikes_df[strikes_df["strike_price"] > 0][["symbol", "strike_price", "option_type"]].drop_duplicates()

print("=" * 80)
print(f"COMMENCING NATURAL GAS OPTIONS BACKFILL: {len(option_symbols)} ACTIVE STRIKES")
print("=" * 80)

now = datetime.now()
start_date = now - timedelta(days=60) # Option contracts opened ~30-45 days ago

all_strikes_data = []
success_count = 0

for idx, row in option_symbols.iterrows():
    sym = row["symbol"]
    strike = row["strike_price"]
    opt_type = row["option_type"]
    
    payload = {
        "symbol": sym,
        "resolution": "1",
        "date_format": "1",
        "range_from": start_date.strftime("%Y-%m-%d"),
        "range_to": now.strftime("%Y-%m-%d"),
        "cont_flag": "0",
        "oi_flag": "1"
    }
    
    retries = 3
    candles = None
    while retries > 0 and candles is None:
        try:
            resp = fyers.history(data=payload)
            if resp.get("s") == "ok" and resp.get("candles"):
                candles = resp["candles"]
            elif resp.get("message") == "No data found":
                candles = []
            else:
                time.sleep(1.0)
                retries -= 1
        except Exception:
            time.sleep(1.0)
            retries -= 1
            
    if candles:
        cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
        df_strike = pd.DataFrame(candles, columns=cols[:len(candles[0])])
        df_strike["symbol"] = sym
        df_strike["strike"] = strike
        df_strike["type"] = opt_type
        all_strikes_data.append(df_strike)
        success_count += 1
        print(f"  [{success_count:02d}/{len(option_symbols)}] {sym:28s} -> {len(df_strike):5,d} candles (Vol: {df_strike['volume'].sum():6,d} lots, Latest OI: {df_strike['oi'].iloc[-1]:,})")
    else:
        print(f"  [--/{len(option_symbols)}] {sym:28s} -> 0 candles (Illiquid / no trades)")
        
    time.sleep(0.35) # Polite sleep for rate-limiting compliance

if all_strikes_data:
    df_all = pd.concat(all_strikes_data, ignore_index=True)
    df_all["ts_ist"] = pd.to_datetime(df_all["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    
    # Save unified master options Parquet
    master_parquet = "data/mcx_vault/naturalgas_options_oct26_1m_all_strikes.parquet"
    df_all.to_parquet(master_parquet, compression="zstd")
    mb = os.path.getsize(master_parquet) / (1024 * 1024)
    
    print("-" * 80)
    print("OPTIONS BACKFILL COMPLETE!")
    print(f"  Active Strikes Captured: {success_count} / {len(option_symbols)}")
    print(f"  Total Option Candles   : {len(df_all):,}")
    print(f"  Consolidated Parquet   : {master_parquet} ({mb:.2f} MB)")
    print("-" * 80)
    
    # Update DuckDB
    con = duckdb.connect("data/mcx_vault/mcx_quant.duckdb")
    con.execute(f"CREATE OR REPLACE VIEW naturalgas_options_oct26_1m AS SELECT * FROM read_parquet('{master_parquet}')")
    cnt = con.execute("SELECT count(*) FROM naturalgas_options_oct26_1m").fetchone()[0]
    con.close()
    print(f"DuckDB view 'naturalgas_options_oct26_1m' registered with {cnt:,} rows!")
