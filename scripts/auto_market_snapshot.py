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
PYTHON_EXE = sys.executable
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

# Add scripts directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 1. Check & Ensure Authentication Token
clear_stale_git_locks()

def get_authenticated_fyers():
    """Retrieves or autonomously generates an active FYERS model instance via TOTP."""
    token = ""
    if os.path.exists(TOKEN_PATH):
        try:
            with open(TOKEN_PATH, encoding="utf-8") as f:
                token = f.read().strip()
        except Exception:
            token = ""
            
    if not token:
        token = os.environ.get("FYERS_ACCESS_TOKEN", "").strip()
        if token:
            os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
            with open(TOKEN_PATH, "w", encoding="utf-8") as f:
                f.write(token)
            log("Loaded FYERS_ACCESS_TOKEN from environment.")

    fyers_inst = fyersModel.FyersModel(client_id="3WWLJD8YE4-200", is_async=False, token=token, log_path="") if token else None
    prof = fyers_inst.get_profile() if fyers_inst else {"s": "error"}

    if prof.get("s") != "ok":
        log(f"WARN: FYERS Token expired or missing ({prof.get('message', 're-auth required')}). Running headless TOTP auto-login...")
        try:
            from auto_fyers_login import auto_login
            if auto_login():
                log("Automated TOTP login succeeded! Fresh token acquired.")
                with open(TOKEN_PATH, encoding="utf-8") as f:
                    token = f.read().strip()
                fyers_inst = fyersModel.FyersModel(client_id="3WWLJD8YE4-200", is_async=False, token=token, log_path="")
                prof = fyers_inst.get_profile()
            else:
                log("ERROR: Headless auto-login failed.")
                with open(TOKEN_STATUS_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "status": "expired",
                        "message": "Token expired and automated TOTP login failed.",
                        "last_check": datetime.now().isoformat()
                    }, f)
                sys.exit(1)
        except Exception as e:
            log(f"ERROR during automated login: {e}")
            sys.exit(1)

    user_name = prof.get("data", {}).get("name", "Authorized User")
    with open(TOKEN_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "status": "active",
            "user": user_name,
            "message": "Token active and verified.",
            "last_check": datetime.now().isoformat()
        }, f)
    return fyers_inst, user_name

fyers, user_name = get_authenticated_fyers()
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

            # If front month October, update the deep chart LOD tiers
            if base == "NATURALGAS" and exp == "26OCT":
                try:
                    deep_1m_file = os.path.join(REPO_DIR, "docs", "data", "deep", "1m", "2026_10.json")
                    if os.path.exists(deep_1m_file):
                        with open(deep_1m_file, "r", encoding="utf-8") as f:
                            existing_bars = json.load(f)
                        bar_map = {b[0]: b for b in existing_bars}
                        oct_start_epoch = int(datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc).timestamp())
                        df_oct = df_combined[df_combined["epoch"] >= oct_start_epoch]
                        for _, row in df_oct.iterrows():
                            bar_map[int(row["epoch"])] = [
                                int(row["epoch"]),
                                round(float(row["open"]), 2),
                                round(float(row["high"]), 2),
                                round(float(row["low"]), 2),
                                round(float(row["close"]), 2),
                                int(row["volume"])
                            ]
                        merged_bars = sorted(bar_map.values(), key=lambda x: x[0])
                        with open(deep_1m_file, "w", encoding="utf-8") as f:
                            json.dump(merged_bars, f, separators=(',', ':'))
                        last_ts = df_oct['ts_ist'].iloc[-1].strftime('%H:%M IST') if len(df_oct) > 0 else 'recent'
                        log(f"Synchronized docs/data/deep/1m/2026_10.json ({len(merged_bars):,} bars up to {last_ts}).")

                    # Synchronize Tier 2: ng_15m.json
                    m15_file = os.path.join(REPO_DIR, "docs", "data", "deep", "ng_15m.json")
                    if os.path.exists(m15_file):
                        # ONLY resample the active recent 5-day window to preserve continuous historical front-month data
                        recent_start_epoch = int((datetime.now(timezone.utc) - timedelta(days=5)).timestamp())
                        df_resample = df_combined[df_combined["epoch"] >= recent_start_epoch].copy()
                        if len(df_resample) > 0:
                            df_resample.index = pd.to_datetime(df_resample["epoch"], unit="s", utc=True)
                            m15_res = df_resample.resample("15min").agg({
                                "open": "first",
                                "high": "max",
                                "low": "min",
                                "close": "last",
                                "volume": "sum",
                                "epoch": "first"
                            }).dropna()
                            m15_new_bars = []
                            for dt_idx, r in m15_res.iterrows():
                                m15_new_bars.append({
                                    "time": int(dt_idx.timestamp()),
                                    "open": round(float(r["open"]), 2),
                                    "high": round(float(r["high"]), 2),
                                    "low": round(float(r["low"]), 2),
                                    "close": round(float(r["close"]), 2),
                                    "volume": int(r["volume"])
                                })
                            with open(m15_file, "r", encoding="utf-8") as f:
                                existing_m15 = json.load(f)
                            existing_map = {b["time"]: b for b in existing_m15}
                            for nb in m15_new_bars:
                                existing_map[nb["time"]] = nb
                            merged_m15 = sorted(existing_map.values(), key=lambda x: x["time"])
                            with open(m15_file, "w", encoding="utf-8") as f:
                                json.dump(merged_m15, f, separators=(',', ':'))
                            log(f"Synchronized docs/data/deep/ng_15m.json ({len(merged_m15):,} bars).")

                    # Synchronize Tier 0: ng_daily.json today's bar
                    daily_file = os.path.join(REPO_DIR, "docs", "data", "deep", "ng_daily.json")
                    if os.path.exists(daily_file):
                        today_str = now.strftime("%Y-%m-%d")
                        today_bars = df_combined[df_combined["ts_ist"].dt.strftime("%Y-%m-%d") == today_str]
                        if len(today_bars) > 0:
                            # In ng_daily.json, daily timestamps are aligned at 03:30:00 UTC (12600s) to match continuous vault
                            today_epoch = int(datetime.strptime(today_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) + 12600
                            today_daily = {
                                "time": today_epoch,
                                "open": round(float(today_bars["open"].iloc[0]), 2),
                                "high": round(float(today_bars["high"].max()), 2),
                                "low": round(float(today_bars["low"].min()), 2),
                                "close": round(float(today_bars["close"].iloc[-1]), 2),
                                "volume": int(today_bars["volume"].sum())
                            }
                            with open(daily_file, "r", encoding="utf-8") as f:
                                daily_bars = json.load(f)
                            existing_daily_map = {b["time"]: b for b in daily_bars}
                            existing_daily_map[today_epoch] = today_daily
                            merged_daily = sorted(existing_daily_map.values(), key=lambda x: x["time"])
                            with open(daily_file, "w", encoding="utf-8") as f:
                                json.dump(merged_daily, f, separators=(',', ':'))
                            log(f"Updated docs/data/deep/ng_daily.json today bar: Close ₹{today_daily['close']:.2f} ({len(merged_daily)} bars)")
                except Exception as e:
                    log(f"Notice updating deep LOD tiers: {e}")
        else:
            log(f"Notice on {sym}: No new candles returned (Market holiday or circuit halt).")
        time.sleep(0.35)
    except Exception as e:
        log(f"Error updating {sym}: {e}")

# 3. Re-run Pre-Computation Pipeline
log("Re-running pre-computation exporters...")
scripts_to_run = []

# Only run TOD seasonality if historical continuous vault exists
vault_continuous = os.path.join(REPO_DIR, "data", "mcx_vault", "NATURALGAS_1m_continuous_2019_2026.parquet")
if os.path.exists(vault_continuous):
    scripts_to_run.append(os.path.join(REPO_DIR, "scripts", "export_tod_seasonality.py"))

scripts_to_run.extend([
    os.path.join(REPO_DIR, "scripts", "export_options_chain.py"),
    os.path.join(REPO_DIR, "scripts", "export_intraday_rollups.py")
])

for script in scripts_to_run:
    try:
        res = subprocess.run([PYTHON_EXE, script], cwd=REPO_DIR, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        log(f"Notice on {os.path.basename(script)}: {e.stderr[:200] if e.stderr else 'error'}")
    except Exception as e:
        log(f"Notice running {os.path.basename(script)}: {e}")

# 4. Fault-Tolerant Git Commit & Push
try:
    clear_stale_git_locks()
    status_res = subprocess.run(["git", "status", "--porcelain", "docs/data/"], cwd=REPO_DIR, capture_output=True, text=True)
    if status_res.stdout.strip():
        log("Changes detected in docs/data/. Syncing with GitHub Pages...")
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=REPO_DIR, check=False)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=REPO_DIR, check=False)
        subprocess.run(["git", "add", "docs/data/"], cwd=REPO_DIR, check=True)
        commit_msg = f"data: automated market snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, check=True)
        
        # Pull rebase with auto-recovery and autostash
        try:
            subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=REPO_DIR, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            log(f"Rebase notice: {e.stderr}. Attempting auto-recovery...")
            subprocess.run(["git", "rebase", "--abort"], cwd=REPO_DIR, capture_output=True)
            subprocess.run(["git", "pull", "--no-rebase", "origin", "main"], cwd=REPO_DIR, check=False)
            
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        log("SUCCESS: Pushed automated market snapshot to GitHub Pages!")
    else:
        log("docs/data/ is fully synchronized. No git push required.")
except Exception as e:
    log(f"Git auto-sync notice: {e}")

log("Snapshot completed cleanly.")
