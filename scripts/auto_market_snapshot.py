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
try:
    import pyarrow
    pyarrow.set_cpu_count(1)
except Exception:
    pass
import pandas as pd
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
    print(entry.strip(), flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

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

MONTH_CODES = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

def resolve_active_contracts(fyers_client, now_dt):
    """Dynamically resolves front-month, near-month, and mini contracts for ANY date of the year."""
    candidates = []
    for offset in range(6):
        m_idx = (now_dt.month - 1 + offset) % 12
        y = now_dt.year + ((now_dt.month - 1 + offset) // 12)
        yy = str(y)[-2:]
        mmm = MONTH_CODES[m_idx]
        exp_code = f"{yy}{mmm}"
        sym_ng = f"MCX:NATURALGAS{exp_code}FUT"
        sym_mini = f"MCX:NATGASMINI{exp_code}FUT"
        candidates.append((y, m_idx + 1, exp_code, sym_ng, sym_mini))
        
    is_roll = (now_dt.day >= 26)
    try:
        q = fyers_client.quotes({"symbols": f"{candidates[0][3]},{candidates[1][3]}"})
        if q.get("s") == "ok":
            for item in q.get("d", []):
                if item.get("n") == candidates[0][3]:
                    v = item.get("v", {})
                    if now_dt.day >= 23 and (v.get("volume", 0) == 0 or v.get("lp", 0) <= 0):
                        is_roll = True
        elif q.get("code") in (-300, 400, 404):
            is_roll = True
    except Exception:
        pass
        
    front_idx = 1 if is_roll else 0
    vault_dir = os.path.join(REPO_DIR, "data", "mcx_vault", "contract_wise")
    os.makedirs(vault_dir, exist_ok=True)
    
    contracts = []
    for i, c in enumerate(candidates):
        is_front = (i == front_idx)
        pfile_ng = os.path.join(vault_dir, f"{c[3].replace(':', '_')}_1m_contract_wise.parquet")
        contracts.append(("NATURALGAS", c[2], c[3], pfile_ng, is_front, c[0], c[1]))
        pfile_mini = os.path.join(vault_dir, f"{c[4].replace(':', '_')}_1m_contract_wise.parquet")
        contracts.append(("NATGASMINI", c[2], c[4], pfile_mini, is_front, c[0], c[1]))
        
    return contracts

def run_snapshot_cycle():
    clear_stale_git_locks()
    fyers, user_name = get_authenticated_fyers()
    log(f"FYERS Session active for {user_name}. Checking active contracts...")

    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(timezone.utc)
    now_ist = now.astimezone(ist_tz)
    active_contracts = resolve_active_contracts(fyers, now_ist)
    start_dt = now - timedelta(days=5)

    for base, exp, sym, pfile, is_front, front_yr, front_mo in active_contracts:
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
                    
                df_combined.to_parquet(pfile, compression="zstd", index=False)
                log(f"Updated {sym}: {len(df_combined):,} bars (+{len(df_new):,} fetched). Latest Close: ₹{df_combined['close'].iloc[-1]:.2f}")

                # If front month, update the deep chart LOD tiers for this symbol
                if is_front:
                    try:
                        sym_prefix = "ngm" if base == "NATGASMINI" else "ng"
                        dir_1m = "1m_ngm" if base == "NATGASMINI" else "1m"
                        manifest_prefix = f"data/deep/{dir_1m}"
                        deep_1m_dir = os.path.join(REPO_DIR, "docs", "data", "deep", dir_1m)
                        os.makedirs(deep_1m_dir, exist_ok=True)

                        # Partition recent candles by calendar month of trading (not contract month)
                        recent_threshold = int((now - timedelta(days=7)).timestamp())
                        df_recent_1m = df_combined[df_combined["epoch"] >= recent_threshold].copy()
                        df_recent_1m["ym"] = df_recent_1m["ts_ist"].dt.strftime("%Y_%m")

                        for ym, grp in df_recent_1m.groupby("ym"):
                            deep_1m_file = os.path.join(deep_1m_dir, f"{ym}.json")
                            existing_bars = []
                            if os.path.exists(deep_1m_file):
                                with open(deep_1m_file, "r", encoding="utf-8") as f:
                                    existing_bars = json.load(f)
                            bar_map = {b[0]: b for b in existing_bars}
                            for _, row in grp.iterrows():
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
                            last_ts = grp['ts_ist'].iloc[-1].strftime('%H:%M IST') if len(grp) > 0 else 'recent'
                            log(f"Synchronized docs/data/deep/{dir_1m}/{ym}.json ({len(merged_bars):,} bars up to {last_ts}).")

                        # Synchronize manifest.json with updated 1m months
                        manifest_path = os.path.join(REPO_DIR, "docs", "data", "deep", "manifest.json")
                        if os.path.exists(manifest_path):
                            try:
                                with open(manifest_path, "r", encoding="utf-8") as f_man:
                                    manifest_obj = json.load(f_man)
                                if sym_prefix in manifest_obj:
                                    m1_list = manifest_obj[sym_prefix].get("m1_months", [])
                                    m1_months_dict = {m["month"]: m for m in m1_list}
                                    for ym, grp in df_recent_1m.groupby("ym"):
                                        deep_1m_file = os.path.join(deep_1m_dir, f"{ym}.json")
                                        if os.path.exists(deep_1m_file):
                                            with open(deep_1m_file, "r", encoding="utf-8") as f_cur:
                                                cur_bars = json.load(f_cur)
                                            if cur_bars:
                                                m1_months_dict[ym] = {
                                                    "month": ym,
                                                    "bars": len(cur_bars),
                                                    "start": cur_bars[0][0],
                                                    "end": cur_bars[-1][0],
                                                    "file": f"{manifest_prefix}/{ym}.json"
                                                }
                                    manifest_obj[sym_prefix]["m1_months"] = sorted(m1_months_dict.values(), key=lambda x: x["month"])
                                    with open(manifest_path, "w", encoding="utf-8") as f_man:
                                        json.dump(manifest_obj, f_man, indent=2)
                            except Exception as e_man:
                                log(f"Notice updating manifest.json for {base}: {e_man}")

                        # Synchronize Tier 2: {sym_prefix}_15m.json
                        m15_file = os.path.join(REPO_DIR, "docs", "data", "deep", f"{sym_prefix}_15m.json")
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
                                log(f"Synchronized docs/data/deep/{sym_prefix}_15m.json ({len(merged_m15):,} bars).")

                        # Synchronize Tier 0: {sym_prefix}_daily.json today's bar
                        daily_file = os.path.join(REPO_DIR, "docs", "data", "deep", f"{sym_prefix}_daily.json")
                        if os.path.exists(daily_file):
                            today_str = now_ist.strftime("%Y-%m-%d")
                            today_bars = df_combined[df_combined["ts_ist"].dt.strftime("%Y-%m-%d") == today_str]
                            if len(today_bars) > 0:
                                today_epoch = int(today_bars["epoch"].iloc[-1])
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
                                ist_tz = timezone(timedelta(hours=5, minutes=30))
                                existing_daily_map = {}
                                for b in daily_bars:
                                    b_date = datetime.fromtimestamp(b["time"], ist_tz).strftime("%Y-%m-%d")
                                    existing_daily_map[b_date] = b
                                existing_daily_map[today_str] = today_daily
                                merged_daily = sorted(existing_daily_map.values(), key=lambda x: x["time"])
                                with open(daily_file, "w", encoding="utf-8") as f:
                                    json.dump(merged_daily, f, separators=(',', ':'))
                                log(f"Updated docs/data/deep/{sym_prefix}_daily.json today bar: Close ₹{today_daily['close']:.2f} ({len(merged_daily)} bars, latest: {datetime.fromtimestamp(today_epoch, ist_tz).strftime('%H:%M IST')})")
                    except Exception as e:
                        log(f"Notice updating deep LOD tiers for {base}: {e}")
            else:
                log(f"Notice on {sym}: No new candles returned (Market holiday or circuit halt).")
            time.sleep(0.35)
        except Exception as e:
            log(f"Error updating {sym}: {e}")

    # 3. Re-run Pre-Computation Pipeline
    log("Re-running pre-computation exporters...")
    scripts_to_run = []

    # Only run TOD seasonality if historical continuous vault exists
    import glob
    vault_matches = glob.glob(os.path.join(REPO_DIR, "data", "mcx_vault", "NATURALGAS_1m_continuous_*.parquet"))
    if vault_matches:
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
        status_res = subprocess.run(["git", "status", "--porcelain", "docs/data/", "data/mcx_vault/contract_wise/"], cwd=REPO_DIR, capture_output=True, text=True)
        if status_res.stdout.strip():
            log("Changes detected in docs/data/ or vault. Syncing with GitHub Pages...")
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=REPO_DIR, check=False)
            subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=REPO_DIR, check=False)
            subprocess.run(["git", "add", "docs/data/", "data/mcx_vault/contract_wise/"], cwd=REPO_DIR, check=True)
            commit_msg = f"data: automated market snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(["git", "commit", "--no-verify", "-m", commit_msg], cwd=REPO_DIR, check=True, capture_output=True, text=True)
            
            # Pull rebase with auto-recovery and retry loop
            pushed = False
            for attempt in range(1, 4):
                try:
                    subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=REPO_DIR, check=True, capture_output=True, text=True)
                    subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True, capture_output=True, text=True)
                    log("SUCCESS: Pushed automated market snapshot to GitHub Pages!")
                    pushed = True
                    break
                except subprocess.CalledProcessError as e:
                    log(f"Push attempt {attempt} notice: {e.stderr or e}. Retrying in 2s...")
                    subprocess.run(["git", "rebase", "--abort"], cwd=REPO_DIR, capture_output=True)
                    time.sleep(2)

            if not pushed:
                log("WARN: Automatic push deferred to next scheduled run.")
            else:
                # Trigger GitHub Pages deployment workflow directly if gh is available
                try:
                    res_gh = subprocess.run(["gh", "workflow", "run", "deploy_pages.yml"], cwd=REPO_DIR, capture_output=True, text=True)
                    if res_gh.returncode == 0:
                        log("SUCCESS: Dispatched deploy_pages.yml workflow!")
                    else:
                        log(f"Notice dispatching deploy_pages: {res_gh.stderr.strip()[:100]}")
                except Exception as e:
                    log(f"Notice dispatching deploy_pages: {e}")
        else:
            log("docs/data/ is fully synchronized. No git push required.")
    except Exception as e:
        log(f"Git auto-sync notice: {e}")

    log("Snapshot completed cleanly.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Automated Market Snapshot & Synchronizer")
    parser.add_argument("--loop", type=int, default=0, help="Loop interval in seconds (e.g. 600 for every 10 mins). If 0, runs once.")
    parser.add_argument("--iterations", type=int, default=1, help="Number of loop iterations. Default 1. If 0, runs forever.")
    args, _ = parser.parse_known_args()

    # Pre-market stand-by:
    # If starting on a weekday between 08:45 AM and 09:00 AM IST, wait until 09:00:05 AM IST so iteration 1 pulls live market open candles!
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    if now_ist.weekday() < 5:
        total_mins = now_ist.hour * 60 + now_ist.minute
        if 525 <= total_mins < 540:  # 08:45 to 08:59 IST
            market_open_time = now_ist.replace(hour=9, minute=0, second=5, microsecond=0)
            wait_sec = (market_open_time - now_ist).total_seconds()
            if 0 < wait_sec <= 900:
                log(f"Pre-market stand-by: current time is {now_ist.strftime('%H:%M:%S IST')}. Waiting {int(wait_sec)}s until 09:00:05 IST market open...")
                time.sleep(wait_sec)

    run_snapshot_cycle()

    if args.loop > 0:
        log(f"Continuous daemon active. Polling every {args.loop}s during MCX trading hours...")
        count = 1
        while True:
            if args.iterations > 0 and count >= args.iterations:
                log(f"Completed {count} iterations. Exiting cleanly.")
                break
            time.sleep(args.loop)
            count += 1
            try:
                now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
                # Weekend check: Saturday=5, Sunday=6
                if now_ist.weekday() >= 5:
                    log("Market closed (Weekend). Skipping poll.")
                    continue
                cur_min = now_ist.hour * 60 + now_ist.minute
                # MCX trading hours: 09:00 to 23:35 IST
                if cur_min < 9 * 60 or cur_min > 23 * 60 + 35:
                    log(f"Market closed (Outside 09:00 - 23:35 IST, current: {now_ist.strftime('%H:%M')} IST). Waiting...")
                    continue
                run_snapshot_cycle()
            except KeyboardInterrupt:
                log("Daemon stopped by user.")
                break
            except Exception as e:
                log(f"Error in snapshot cycle: {e}. Retrying in {args.loop}s...")
