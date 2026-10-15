import os
import time
from datetime import datetime, timedelta
import pandas as pd
import duckdb
from fyers_apiv3 import fyersModel

CLIENT_ID = "3WWLJD8YE4-200"
VAULT_DIR = "data/mcx_vault"

with open("data/fyers_auth/access_token.txt") as f:
    token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=token, log_path="")

# 1. Fetch Mini option chain
print("Fetching active Natural Gas Mini option chain...")
resp_mini = fyers.optionchain(data={"symbol": "MCX:NATGASMINI26OCTFUT", "strikecount": 20})
if resp_mini.get("s") == "ok":
    strikes_mini = resp_mini.get("data", {}).get("optionsChain", [])
    df_m = pd.DataFrame(strikes_mini)
    active_mini_strikes = df_m[df_m["strike_price"] > 0][["symbol", "strike_price", "option_type"]].drop_duplicates()
    
    print(f"Total Mini Strikes to backfill: {len(active_mini_strikes)}")
    
    now = datetime.now()
    start_date = now - timedelta(days=60)
    
    mini_chunks = []
    success_cnt = 0
    
    for idx, row in active_mini_strikes.iterrows():
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
        
        try:
            r = fyers.history(data=payload)
            if r.get("s") == "ok" and r.get("candles"):
                candles = r["candles"]
                cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
                df_c = pd.DataFrame(candles, columns=cols[:len(candles[0])])
                df_c["symbol"] = sym
                df_c["strike"] = strike
                df_c["type"] = opt_type
                mini_chunks.append(df_c)
                success_cnt += 1
                print(f"  [{success_cnt:02d}/{len(active_mini_strikes)}] {sym:28s} -> {len(df_c):5,d} candles (Vol: {df_c['volume'].sum():6,d} lots, OI: {df_c['oi'].iloc[-1]:,})")
            time.sleep(0.35) # Strict rate-limit safety
        except Exception as e:
            print(f"  Error on {sym}: {e}")
            time.sleep(1.0)
            
    if mini_chunks:
        df_all_mini = pd.concat(mini_chunks, ignore_index=True)
        df_all_mini["ts_ist"] = pd.to_datetime(df_all_mini["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
        
        mini_parquet = os.path.join(VAULT_DIR, "options", "natgasmini_options_oct26_1m_all_strikes.parquet")
        os.makedirs(os.path.dirname(mini_parquet), exist_ok=True)
        df_all_mini.to_parquet(mini_parquet, compression="zstd")
        mb = os.path.getsize(mini_parquet) / (1024 * 1024)
        
        print("-" * 80)
        print("NATGAS MINI OPTIONS BACKFILL COMPLETE!")
        print(f"  Active Mini Strikes: {success_cnt} / {len(active_mini_strikes)}")
        print(f"  Total Mini Candles : {len(df_all_mini):,}")
        print(f"  Saved to           : {mini_parquet} ({mb:.2f} MB)")
        print("-" * 80)
        
        # Register in DuckDB
        con = duckdb.connect(os.path.join(VAULT_DIR, "mcx_quant.duckdb"))
        con.execute(f"CREATE OR REPLACE VIEW natgasmini_options_oct26_1m AS SELECT * FROM read_parquet('{mini_parquet}')")
        cnt = con.execute("SELECT count(*) FROM natgasmini_options_oct26_1m").fetchone()[0]
        con.close()
        print(f"DuckDB view 'natgasmini_options_oct26_1m' registered with {cnt:,} rows!")
