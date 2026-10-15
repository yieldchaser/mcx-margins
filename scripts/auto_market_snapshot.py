"""
Blue Margin — Silent Automated Market Snapshot & Cloud Synchronizer
scripts/auto_market_snapshot.py

Runs completely invisibly in background:
1. Pulls latest 1-min candles up to current minute for active contracts
2. Updates local quant vault parquet files
3. Re-runs Black-76, TOD seasonality, and 15m rollups
4. Automatically commits and pushes docs/data/ to GitHub Pages
5. Logs activity silently to data/auto_sync.log
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time
import subprocess
from datetime import datetime, timedelta, timezone
import pandas as pd
import duckdb
from fyers_apiv3 import fyersModel

LOG_FILE = "data/auto_sync.log"
os.makedirs("data", exist_ok=True)
os.makedirs("data/mcx_vault/contract_wise", exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print(entry.strip())

# 1. Check Authentication Token
token_path = "data/fyers_auth/access_token.txt"
if not os.path.exists(token_path):
    log("ERROR: No access_token.txt found. Run login first.")
    sys.exit(1)

with open(token_path) as f:
    token = f.read().strip()

fyers = fyersModel.FyersModel(client_id="3WWLJD8YE4-200", is_async=False, token=token, log_path="")

# Verify Profile
try:
    prof = fyers.get_profile()
    if prof.get("s") != "ok":
        log(f"WARN: FYERS Token expired or invalid: {prof.get('message', 'unknown')}")
        sys.exit(0) # Silent exit, no prompt
except Exception as e:
    log(f"ERROR: Exception validating profile: {e}")
    sys.exit(1)

log("FYERS Session active. Checking active contracts...")

# 2. Contracts to update
active_contracts = [
    ("NATURALGAS", "26OCT", "MCX:NATURALGAS26OCTFUT", "data/mcx_vault/contract_wise/MCX_NATURALGAS26OCTFUT_1m_contract_wise.parquet"),
    ("NATURALGAS", "26NOV", "MCX:NATURALGAS26NOVFUT", "data/mcx_vault/contract_wise/MCX_NATURALGAS26NOVFUT_1m_contract_wise.parquet"),
    ("NATGASMINI", "26OCT", "MCX:NATGASMINI26OCTFUT", "data/mcx_vault/contract_wise/MCX_NATGASMINI26OCTFUT_1m_contract_wise.parquet")
]

now = datetime.now()
start_dt = now - timedelta(days=5) # Last 5 days to ensure no gaps

for base, exp, sym, pfile in active_contracts:
    payload = {
        "symbol": sym,
        "resolution": "1",
        "date_format": "1",
        "range_from": start_dt.strftime("%Y-%m-%d"),
        "range_to": now.strftime("%Y-%m-%d"),
        "cont_flag": "0",
        "oi_flag": "1"
    }
    
    try:
        r = fyers.history(data=payload)
        if r.get("s") == "ok" and r.get("candles"):
            candles = r["candles"]
            cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
            df_new = pd.DataFrame(candles, columns=cols[:len(candles[0])])
            df_new["symbol"] = sym
            df_new["commodity"] = base
            df_new["expiry"] = exp
            df_new["ts_ist"] = pd.to_datetime(df_new["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
            
            # Merge with existing parquet
            if os.path.exists(pfile):
                df_existing = pd.read_parquet(pfile)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=["epoch"]).sort_values("epoch").reset_index(drop=True)
            else:
                df_combined = df_new
                
            df_combined.to_parquet(pfile, compression="zstd")
            log(f"Updated {sym}: {len(df_combined):,} bars (+{len(df_new):,} fetched). Latest Close: ₹{df_combined['close'].iloc[-1]:.2f}")
        time.sleep(0.35)
    except Exception as e:
        log(f"Error updating {sym}: {e}")

# 3. Re-run Pre-Computation Pipeline
log("Re-running pre-computation exporters...")
try:
    subprocess.run([sys.executable, "scripts/export_tod_seasonality.py"], check=True, capture_output=True)
    subprocess.run([sys.executable, "scripts/export_options_chain.py"], check=True, capture_output=True)
    subprocess.run([sys.executable, "scripts/export_intraday_rollups.py"], check=True, capture_output=True)
    log("Pre-computation exporters completed successfully.")
except Exception as e:
    log(f"Error in exporters: {e}")

# 4. Git Diff Check and Auto-Push to GitHub Pages
try:
    diff_check = subprocess.run(["git", "status", "--porcelain", "docs/data/"], capture_output=True, text=True)
    if diff_check.stdout.strip():
        log("Changes detected in docs/data/. Committing and pushing to GitHub Pages...")
        subprocess.run(["git", "add", "docs/data/"], check=True)
        commit_msg = f"data: automated market snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        # Pull rebase before push to avoid conflicts
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        log("SUCCESS: Pushed automated market snapshot to GitHub Pages!")
    else:
        log("No changes in docs/data/. Everything up-to-date.")
except Exception as e:
    log(f"Git auto-push encountered notice: {e}")

log("Snapshot completed cleanly.")
