import os
import time
from datetime import datetime, timedelta
import pandas as pd
import duckdb
from fyers_apiv3 import fyersModel

CLIENT_ID = "3WWLJD8YE4-200"
CONTRACT_DIR = "data/mcx_vault/contract_wise"
os.makedirs(CONTRACT_DIR, exist_ok=True)

with open("data/fyers_auth/access_token.txt") as f:
    token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=token, log_path="")

# Active & upcoming contract series for Natural Gas and Mini
contracts = [
    # Natural Gas Standard
    ("NATURALGAS", "26OCT", "MCX:NATURALGAS26OCTFUT"),
    ("NATURALGAS", "26NOV", "MCX:NATURALGAS26NOVFUT"),
    ("NATURALGAS", "26DEC", "MCX:NATURALGAS26DECFUT"),
    ("NATURALGAS", "27JAN", "MCX:NATURALGAS27JANFUT"),
    ("NATURALGAS", "27FEB", "MCX:NATURALGAS27FEBFUT"),
    ("NATURALGAS", "27MAR", "MCX:NATURALGAS27MARFUT"),
    # Natural Gas Mini
    ("NATGASMINI", "26OCT", "MCX:NATGASMINI26OCTFUT"),
    ("NATGASMINI", "26NOV", "MCX:NATGASMINI26NOVFUT"),
    ("NATGASMINI", "26DEC", "MCX:NATGASMINI26DECFUT"),
    ("NATGASMINI", "27JAN", "MCX:NATGASMINI27JANFUT"),
    ("NATGASMINI", "27FEB", "MCX:NATGASMINI27FEBFUT"),
    ("NATGASMINI", "27MAR", "MCX:NATGASMINI27MARFUT")
]

print("=" * 80)
print("DOWNLOADING CONTRACT-WISE (UNSTITCHED, cont_flag=0) 1-MIN FUTURES DATA")
print("=" * 80)

now = datetime.now()
start_dt = now - timedelta(days=90) # Up to 90 days of contract-specific history

all_contract_records = []

for base, exp, sym in contracts:
    payload = {
        "symbol": sym,
        "resolution": "1",
        "date_format": "1",
        "range_from": start_dt.strftime("%Y-%m-%d"),
        "range_to": now.strftime("%Y-%m-%d"),
        "cont_flag": "0", # STRICTLY CONTRACT-SPECIFIC (UNSTITCHED)
        "oi_flag": "1"
    }
    
    try:
        r = fyers.history(data=payload)
        if r.get("s") == "ok" and r.get("candles"):
            candles = r["candles"]
            cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
            df = pd.DataFrame(candles, columns=cols[:len(candles[0])])
            df["symbol"] = sym
            df["commodity"] = base
            df["expiry"] = exp
            df["ts_ist"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
            
            clean_name = sym.replace(":", "_")
            out_file = os.path.join(CONTRACT_DIR, f"{clean_name}_1m_contract_wise.parquet")
            df.to_parquet(out_file, compression="zstd")
            all_contract_records.append(df)
            
            print(f"  {sym:26s} -> {len(df):6,d} candles (Total Vol: {df['volume'].sum():7,d} lots, Latest OI: {df['oi'].iloc[-1]:,}) -> Saved to {out_file}")
        else:
            print(f"  {sym:26s} -> 0 candles ({r.get('message', r)})")
        time.sleep(0.35) # Rate-limit safety
    except Exception as e:
        print(f"  Error on {sym}: {e}")
        time.sleep(1.0)

if all_contract_records:
    df_unified = pd.concat(all_contract_records, ignore_index=True)
    master_file = "data/mcx_vault/naturalgas_futures_contract_wise_1m.parquet"
    df_unified.to_parquet(master_file, compression="zstd")
    mb = os.path.getsize(master_file) / (1024 * 1024)
    print("-" * 80)
    print(f"Saved unified contract-wise master file: {master_file} ({len(df_unified):,} rows, {mb:.2f} MB)")
    
    # Register in DuckDB
    con = duckdb.connect("data/mcx_vault/mcx_quant.duckdb")
    con.execute(f"CREATE OR REPLACE VIEW naturalgas_futures_contract_wise_1m AS SELECT * FROM read_parquet('{master_file}')")
    cnt = con.execute("SELECT count(*) FROM naturalgas_futures_contract_wise_1m").fetchone()[0]
    con.close()
    print(f"Registered view 'naturalgas_futures_contract_wise_1m' in DuckDB with {cnt:,} rows!")
