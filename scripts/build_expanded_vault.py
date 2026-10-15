import os
import json
import time
from datetime import datetime, timedelta
import pandas as pd
import duckdb
from fyers_apiv3 import fyersModel

CLIENT_ID = "3WWLJD8YE4-200"
VAULT_DIR = "data/mcx_vault"
EXPANDED_DIR = os.path.join(VAULT_DIR, "expanded")
os.makedirs(EXPANDED_DIR, exist_ok=True)

with open("data/fyers_auth/access_token.txt") as f:
    token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=token, log_path="")

# -------------------------------------------------------------
# 1. CAPTURE & SAVE LIVE NATURAL GAS OPTION CHAIN SNAPSHOT
# -------------------------------------------------------------
print("=" * 80)
print("1. ARCHIVING NATURAL GAS LIVE OPTION CHAIN SNAPSHOT")
print("=" * 80)
try:
    opt_resp = fyers.optionchain(data={"symbol": "MCX:NATURALGAS26OCTFUT", "strikecount": 15})
    if opt_resp.get("s") == "ok":
        opt_data = opt_resp.get("data", {})
        # Save raw JSON
        json_path = os.path.join(EXPANDED_DIR, "naturalgas_live_optionchain.json")
        with open(json_path, "w") as f:
            json.dump(opt_data, f, indent=2)
        
        # Save structured strikes to Parquet
        strikes = opt_data.get("optionsChain", [])
        if strikes:
            df_opt = pd.DataFrame(strikes)
            opt_parquet = os.path.join(EXPANDED_DIR, "naturalgas_optionchain_strikes.parquet")
            df_opt.to_parquet(opt_parquet, compression="zstd")
            print(f"Archived {len(df_opt)} option strikes to {opt_parquet} and {json_path}")
            print(f"Total Call OI: {opt_data.get('callOi'):,} | Total Put OI: {opt_data.get('putOi'):,} | PCR: {opt_data.get('putOi')/max(opt_data.get('callOi'),1):.2f}")
except Exception as e:
    print("Error saving option chain:", e)

# -------------------------------------------------------------
# 2. DOWNLOAD ATM OPTION HISTORICAL 1-MIN BARS (310 CE & 310 PE)
# -------------------------------------------------------------
print("\n" + "=" * 80)
print("2. DOWNLOADING NATURAL GAS ATM OPTION 1-MIN BARS (310 CE & 310 PE)")
print("=" * 80)
opt_symbols = ["MCX:NATURALGAS26OCT310CE", "MCX:NATURALGAS26OCT310PE"]
for sym in opt_symbols:
    try:
        now = datetime.now()
        start = now - timedelta(days=30)
        p = {
            "symbol": sym,
            "resolution": "1",
            "date_format": "1",
            "range_from": start.strftime("%Y-%m-%d"),
            "range_to": now.strftime("%Y-%m-%d"),
            "cont_flag": "0",
            "oi_flag": "1"
        }
        r = fyers.history(data=p)
        if r.get("s") == "ok" and r.get("candles"):
            candles = r["candles"]
            cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
            df = pd.DataFrame(candles, columns=cols[:len(candles[0])])
            df["ts_ist"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
            clean_name = sym.replace(":", "_")
            out_file = os.path.join(EXPANDED_DIR, f"{clean_name}_1m.parquet")
            df.to_parquet(out_file, compression="zstd")
            print(f"Saved {len(df):,} 1-min candles for {sym} to {out_file} ({os.path.getsize(out_file)/1024:.1f} KB)")
        time.sleep(0.4)
    except Exception as e:
        print(f"Error fetching {sym}: {e}")

# -------------------------------------------------------------
# 3. DOWNLOAD 1-YEAR CONTINUOUS 1-MIN BARS FOR KEY MCX COMMODITIES
# -------------------------------------------------------------
print("\n" + "=" * 80)
print("3. DOWNLOADING 1-YEAR CONTINUOUS 1-MIN BARS FOR KEY COMMODITIES")
print("=" * 80)
commodities_to_fetch = [
    ("CRUDEOIL", "MCX:CRUDEOIL26OCTFUT"),
    ("GOLD", "MCX:GOLD26DECFUT"),
    ("SILVER", "MCX:SILVER26DECFUT"),
    ("COPPER", "MCX:COPPER26OCTFUT")
]

for name, sym in commodities_to_fetch:
    now = datetime.now()
    start_dt = now - timedelta(days=365) # 1 Full Year
    chunks = []
    curr_end = now
    print(f"\nDownloading {name} ({sym})...")
    
    while curr_end > start_dt:
        curr_start = max(start_dt, curr_end - timedelta(days=90))
        payload = {
            "symbol": sym,
            "resolution": "1",
            "date_format": "1",
            "range_from": curr_start.strftime("%Y-%m-%d"),
            "range_to": curr_end.strftime("%Y-%m-%d"),
            "cont_flag": "1",
            "oi_flag": "1"
        }
        
        try:
            resp = fyers.history(data=payload)
            if resp.get("s") == "ok" and resp.get("candles"):
                candles = resp["candles"]
                cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
                df_chunk = pd.DataFrame(candles, columns=cols[:len(candles[0])])
                chunks.append(df_chunk)
                print(f"  Chunk {curr_start.strftime('%Y-%m-%d')} -> {curr_end.strftime('%Y-%m-%d')}: {len(df_chunk):,} bars")
            time.sleep(0.4) # Strict rate-limit safety
        except Exception as e:
            print(f"  Error on chunk: {e}")
            time.sleep(2.0)
            
        curr_end = curr_start - timedelta(days=1)
        
    if chunks:
        df_comm = pd.concat(chunks, ignore_index=True)
        df_comm = df_comm.drop_duplicates(subset=["epoch"]).sort_values("epoch").reset_index(drop=True)
        df_comm["ts_ist"] = pd.to_datetime(df_comm["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
        out_comm = os.path.join(EXPANDED_DIR, f"{name}_1m_continuous_1yr.parquet")
        df_comm.to_parquet(out_comm, compression="zstd")
        mb = os.path.getsize(out_comm) / (1024 * 1024)
        print(f"--> COMPLETED {name}: {len(df_comm):,} candles saved to {out_comm} ({mb:.2f} MB)")

# -------------------------------------------------------------
# 4. UPDATE UNIFIED DUCKDB DATABASE
# -------------------------------------------------------------
print("\n" + "=" * 80)
print("4. UPDATING UNIFIED DUCKDB QUANT VAULT")
print("=" * 80)
db_path = os.path.join(VAULT_DIR, "mcx_quant.duckdb")
con = duckdb.connect(db_path)

for root, _, files in os.walk(VAULT_DIR):
    for f in files:
        if f.endswith(".parquet"):
            tbl_name = f.replace(".parquet", "").replace("-", "_").replace(".", "_")
            full_path = os.path.join(root, f).replace("\\", "/")
            con.execute(f"CREATE OR REPLACE VIEW {tbl_name} AS SELECT * FROM read_parquet('{full_path}')")
            cnt = con.execute(f"SELECT count(*) FROM {tbl_name}").fetchone()[0]
            print(f"  Indexed View: {tbl_name:40s} | Rows: {cnt:,}")

con.close()
print(f"\nALL DOWNLOADS COMPLETE! Quant vault successfully updated at {db_path}!")
