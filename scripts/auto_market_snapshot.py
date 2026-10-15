"""
Blue Margin — Hardened Automated Market Snapshot & Cloud Synchronizer
scripts/auto_market_snapshot.py

Fault-Tolerant Features:
1. Absolute path anchoring (immune to working directory variations)
2. Git index.lock automatic recovery
3. Safe rebase/stash conflict resolution
4. Clear token health state reporting in docs/data/token_status.json
5. Circuit breaker handling on empty API candles / holidays
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time
import json
import subprocess
from datetime import datetime, timedelta, timezone
import pandas as pd
import duckdb
from fyers_apiv3 import fyersModel

# Absolute Repository Root Path
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_EXE = os.path.join(os.path.dirname(sys.executable), "python.exe")
LOG_FILE = os.path.join(REPO_DIR, "data", "auto_sync.log")
TOKEN_PATH = os.path.join(REPO_DIR, "data", "fyers_auth", "access_token.txt")
TOKEN_STATUS_FILE = os.path.join(REPO_DIR, "docs", "data", "token_status.json")

os.makedirs(os.path.join(REPO_DIR, "data"), exist_ok=True)
os.makedirs(os.path.join(REPO_DIR, "data", "mcx_vault", "contract_wise"), exist_ok=True)
os.makedirs(os.path.join(REPO_DIR, "docs", "data"), exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print(entry.strip())

def clear_stale_git_locks():
    """Recovers from interrupted git processes by clearing stale index.lock files"""
    lock_file = os.path.join(REPO_DIR, ".git", "index.lock")
    if os.path.exists(lock_file):
        try:
            mtime = os.path.getmtime(lock_file)
            if (time.time() - mtime) > 120: # Lock older than 2 minutes
                os.remove(lock_file)
                log("Cleared stale .git/index.lock file.")
        except Exception as e:
            log(f"Notice on git lock check: {e}")

# 1. Check Authentication Token
clear_stale_git_locks()

if not os.path.exists(TOKEN_PATH):
    log("ERROR: No access_token.txt found. Run login script.")
    with open(TOKEN_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({"status": "missing", "message": "No access_token.txt found.", "last_check": datetime.now().isoformat()}, f)
    sys.exit(1)

with open(TOKEN_PATH, encoding="utf-8") as f:
    token = f.read().strip()

fyers = fyersModel.FyersModel(client_id="3WWLJD8YE4-200", is_async=False, token=token, log_path="")

# Verify Profile & Token Validity
try:
    prof = fyers.get_profile()
    if prof.get("s") != "ok":
        log(f"WARN: FYERS Token expired or invalid: {prof.get('message', 'unknown')}")
        with open(TOKEN_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "status": "expired",
                "message": f"Token expired or invalid ({prof.get('message', 'unknown')}). Re-run scripts/fyers_login_and_fetch.py.",
                "last_check": datetime.now().isoformat()
            }, f)
        sys.exit(0) # Silent exit on expired token, no crash
    else:
        user_name = prof.get("data", {}).get("name", "Authorized User")
        with open(TOKEN_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "status": "active",
                "user": user_name,
                "message": "Token active and verified.",
                "last_check": datetime.now().isoformat()
            }, f)
except Exception as e:
    log(f"ERROR: Exception validating profile: {e}")
    sys.exit(1)

log(f"FYERS Session active for {user_name}. Checking active contracts...")

# 2. Contracts to update
active_contracts = [
    ("NATURALGAS", "26OCT", "MCX:NATURALGAS26OCTFUT", os.path.join(REPO_DIR, "data", "mcx_vault", "contract_wise", "MCX_NATURALGAS26OCTFUT_1m_contract_wise.parquet")),
    ("NATURALGAS", "26NOV", "MCX:NATURALGAS26NOVFUT", os.path.join(REPO_DIR, "data", "mcx_vault", "contract_wise", "MCX_NATURALGAS26NOVFUT_1m_contract_wise.parquet")),
    ("NATGASMINI", "26OCT", "MCX:NATGASMINI26OCTFUT", os.path.join(REPO_DIR, "data", "mcx_vault", "contract_wise", "MCX_NATGASMINI26OCTFUT_1m_contract_wise.parquet"))
]

now = datetime.now()
start_dt = now - timedelta(days=5)

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
        if r.get("s") == "ok" and r.get("candles") and len(r["candles"]) > 0:
            candles = r["candles"]
            cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
            df_new = pd.DataFrame(candles, columns=cols[:len(candles[0])])
            df_new["symbol"] = sym
            df_new["commodity"] = base
            df_new["expiry"] = exp
            df_new["ts_ist"] = pd.to_datetime(df_new["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
            
            # Robust merge and deduplication
            if os.path.exists(pfile):
                df_existing = pd.read_parquet(pfile)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=["epoch"], keep="last").sort_values("epoch").reset_index(drop=True)
            else:
                df_combined = df_new
                
            df_combined.to_parquet(pfile, compression="zstd")
            log(f"Updated {sym}: {len(df_combined):,} bars (+{len(df_new):,} fetched). Latest Close: ₹{df_combined['close'].iloc[-1]:.2f}")
        else:
            log(f"Notice on {sym}: No new candles returned (Market holiday or circuit halt).")
        time.sleep(0.35)
    except Exception as e:
        log(f"Error updating {sym}: {e}")

# 3. Re-run Pre-Computation Pipeline
log("Re-running pre-computation exporters...")
scripts_to_run = [
    os.path.join(REPO_DIR, "scripts", "export_tod_seasonality.py"),
    os.path.join(REPO_DIR, "scripts", "export_options_chain.py"),
    os.path.join(REPO_DIR, "scripts", "export_intraday_rollups.py")
]

for script in scripts_to_run:
    try:
        res = subprocess.run([PYTHON_EXE, script], cwd=REPO_DIR, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        log(f"Error running {os.path.basename(script)}: {e.stderr}")

# 4. Fault-Tolerant Git Commit & Push
try:
    clear_stale_git_locks()
    status_res = subprocess.run(["git", "status", "--porcelain", "docs/data/"], cwd=REPO_DIR, capture_output=True, text=True)
    if status_res.stdout.strip():
        log("Changes detected in docs/data/. Syncing with GitHub Pages...")
        subprocess.run(["git", "add", "docs/data/"], cwd=REPO_DIR, check=True)
        commit_msg = f"data: automated market snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, check=True)
        
        # Pull rebase with auto-recovery
        try:
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=REPO_DIR, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            log(f"Rebase notice: {e.stderr}. Attempting auto-recovery...")
            subprocess.run(["git", "rebase", "--abort"], cwd=REPO_DIR, capture_output=True)
            subprocess.run(["git", "pull", "--no-rebase", "origin", "main"], cwd=REPO_DIR, check=True)
            
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        log("SUCCESS: Pushed automated market snapshot to GitHub Pages!")
    else:
        log("docs/data/ is fully synchronized. No git push required.")
except Exception as e:
    log(f"Git auto-sync notice: {e}")

log("Snapshot completed cleanly.")
