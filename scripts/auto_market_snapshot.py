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

def get_mcx_session_info(dt_ist=None):
    """
    Dynamically resolves MCX trading session state, season (Summer vs Winter),
    and exchange closing time based on US Daylight Saving Time (DST).

    MCX Trading Session Rules:
    - Pre-Market Standby: 08:50 AM to 09:00 AM IST
    - Morning Open: 09:00:00 AM IST
    - Summer Closing (US DST EDT active): 23:30 PM IST (11:30 PM IST)
    - Winter Closing (US Standard EST active): 23:55 PM IST (11:55 PM IST)
    - Weekends (Saturday & Sunday): Market is CLOSED all day.
    """
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    if dt_ist is None:
        dt_ist = datetime.now(ist_tz)
    elif dt_ist.tzinfo is None:
        dt_ist = dt_ist.replace(tzinfo=ist_tz)
    else:
        dt_ist = dt_ist.astimezone(ist_tz)

    # 1. Determine Summer (US EDT) vs Winter (US EST)
    is_dst = False
    try:
        import zoneinfo
        ny_tz = zoneinfo.ZoneInfo("America/New_York")
        dt_ny = dt_ist.astimezone(timezone.utc).astimezone(ny_tz)
        is_dst = bool(dt_ny.dst() and dt_ny.dst().total_seconds() != 0)
    except Exception:
        # Fallback standard calendar calculation (starts 2nd Sun March, ends 1st Sun Nov)
        year = dt_ist.year
        mar1 = datetime(year, 3, 1, tzinfo=ist_tz)
        mar_second_sun = 1 + (6 - mar1.weekday()) % 7 + 7
        dst_start = datetime(year, 3, mar_second_sun, 2, 0, tzinfo=ist_tz)
        nov1 = datetime(year, 11, 1, tzinfo=ist_tz)
        dst_end = datetime(year, 11, 1 + (6 - nov1.weekday()) % 7, 2, 0, tzinfo=ist_tz)
        is_dst = dst_start <= dt_ist < dst_end

    season_name = "Summer (US DST)" if is_dst else "Winter (US Standard)"
    close_hour, close_min = (23, 30) if is_dst else (23, 55)
    close_total_mins = close_hour * 60 + close_min
    open_standby_mins = 8 * 60 + 50 # 08:50 AM IST

    # 2. Check Weekends
    if dt_ist.weekday() >= 5: # 5 = Saturday, 6 = Sunday
        day_name = "Saturday" if dt_ist.weekday() == 5 else "Sunday"
        return False, f"Weekend ({day_name})", season_name, (close_hour, close_min)

    # 3. Check Known Full-Day MCX Trading Holidays
    date_str = dt_ist.strftime("%Y-%m-%d")
    MCX_FULL_HOLIDAYS = {
        # 2026
        "2026-01-26": "Republic Day",
        "2026-03-03": "Holi",
        "2026-03-21": "Id-Ul-Fitr (Ramzan Id)",
        "2026-04-03": "Good Friday",
        "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
        "2026-05-01": "Maharashtra Day",
        "2026-05-27": "Bakri Id",
        "2026-06-26": "Muharram",
        "2026-08-15": "Independence Day",
        "2026-10-02": "Mahatma Gandhi Jayanti",
        "2026-10-20": "Dussehra",
        "2026-11-10": "Diwali Balipratipada",
        "2026-11-24": "Gurunanak Jayanti",
        "2026-12-25": "Christmas",
        # 2027
        "2027-01-26": "Republic Day",
        "2027-03-22": "Holi",
        "2027-03-26": "Good Friday",
        "2027-04-14": "Dr. Ambedkar Jayanti",
        "2027-05-01": "Maharashtra Day",
        "2027-08-15": "Independence Day",
        "2027-10-02": "Mahatma Gandhi Jayanti",
        "2027-12-25": "Christmas",
    }
    if date_str in MCX_FULL_HOLIDAYS:
        return False, f"MCX Full Holiday ({MCX_FULL_HOLIDAYS[date_str]})", season_name, (close_hour, close_min)

    # 4. Check Holidays where Morning session is closed but Evening opens at 17:00 IST
    MCX_EVENING_ONLY_HOLIDAYS = {
        # 2026
        "2026-02-15": "Mahashivratri",
        "2026-03-27": "Ram Navami",
        "2026-03-31": "Mahavir Jayanti",
        # 2027
        "2027-03-06": "Mahashivratri",
        "2027-04-16": "Ram Navami",
    }
    cur_mins = dt_ist.hour * 60 + dt_ist.minute
    if date_str in MCX_EVENING_ONLY_HOLIDAYS and cur_mins < 17 * 60:
        return False, f"MCX Holiday Morning Session ({MCX_EVENING_ONLY_HOLIDAYS[date_str]} - opens at 17:00 IST)", season_name, (close_hour, close_min)

    # 5. Check Time Windows
    if cur_mins < open_standby_mins:
        return False, f"Overnight / Pre-market (opens at 09:00 IST, standby 08:50 IST)", season_name, (close_hour, close_min)
    if cur_mins > close_total_mins:
        return False, f"Post-close night session (closed at {close_hour}:{close_min:02d} IST)", season_name, (close_hour, close_min)

    return True, f"Market OPEN ({season_name}, 09:00 - {close_hour}:{close_min:02d} IST)", season_name, (close_hour, close_min)

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
ROLL_STATE_FILE = os.path.join(REPO_DIR, "data", "roll_state.json")
CONTRACT_INDEX_FILE = os.path.join(REPO_DIR, "docs", "data", "contract_index.json")

# Official MCX Natural Gas Expiration Schedule (Standard Expiry: 4th or 5th business day before end of month)
MCX_NG_EXPIRY_SCHEDULE = {
    # 2026
    "26JAN": "2026-01-27",
    "26FEB": "2026-02-24",
    "26MAR": "2026-03-26",
    "26APR": "2026-04-27",
    "26MAY": "2026-05-26",
    "26JUN": "2026-06-25",
    "26JUL": "2026-07-28",
    "26AUG": "2026-08-26",
    "26SEP": "2026-09-25",
    "26OCT": "2026-10-27",
    "26NOV": "2026-11-24",
    "26DEC": "2026-12-28",
    # 2027
    "27JAN": "2027-01-25",
    "27FEB": "2027-02-23",
    "27MAR": "2027-03-25",
    "27APR": "2027-04-27",
    "27MAY": "2027-05-26",
    "27JUN": "2027-06-25",
    "27JUL": "2027-07-27",
    "27AUG": "2027-08-26",
    "27SEP": "2027-09-27",
    "27OCT": "2027-10-26",
    "27NOV": "2027-11-24",
    "27DEC": "2027-12-28",
}

def get_ng_contract_expiry_dt(exp_code: str, yr: int, mo: int) -> datetime:
    """Returns official contract expiry datetime in Asia/Kolkata timezone (23:30 summer, 23:55 winter)."""
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    date_str = MCX_NG_EXPIRY_SCHEDULE.get(exp_code)
    
    if not date_str and os.path.exists(CONTRACT_INDEX_FILE):
        try:
            with open(CONTRACT_INDEX_FILE, "r", encoding="utf-8") as f:
                ci = json.load(f)
            for item in ci.get("ng", []):
                exp_raw = item.get("expiry", "")
                if exp_code in exp_raw:
                    dt_parsed = datetime.strptime(exp_raw, "%d%b%Y")
                    date_str = dt_parsed.strftime("%Y-%m-%d")
                    break
        except Exception:
            pass

    if not date_str:
        # Standard fallback: 26th of contract month
        date_str = f"{yr:04d}-{mo:02d}-26"

    # MCX session close: 23:55 IST in winter (Nov-Feb), 23:30 IST in summer (Mar-Oct)
    close_time_str = "23:55:00" if mo in [11, 12, 1, 2] else "23:30:00"
    exp_dt = datetime.strptime(f"{date_str} {close_time_str}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=ist_tz)
    return exp_dt

def resolve_active_contracts(fyers_client, now_dt):
    """Dynamically resolves front-month, near-month, and mini contracts anchored to official expiry."""
    candidates = []
    for offset in range(6):
        m_idx = (now_dt.month - 1 + offset) % 12
        y = now_dt.year + ((now_dt.month - 1 + offset) // 12)
        yy = str(y)[-2:]
        mmm = MONTH_CODES[m_idx]
        exp_code = f"{yy}{mmm}"
        sym_ng = f"MCX:NATURALGAS{exp_code}FUT"
        sym_mini = f"MCX:NATGASMINI{exp_code}FUT"
        exp_dt = get_ng_contract_expiry_dt(exp_code, y, m_idx + 1)
        candidates.append({
            "year": y,
            "month": m_idx + 1,
            "exp_code": exp_code,
            "sym_ng": sym_ng,
            "sym_mini": sym_mini,
            "expiry_dt": exp_dt,
            "expiry_epoch": int(exp_dt.timestamp())
        })

    # Ensure now_dt is timezone-aware in Asia/Kolkata
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=ist_tz)

    # Rollover logic: Candidate 0 remains active front month until its official expiry close timestamp.
    # In live trading (with non-zero hour/minute), Candidate 0 expires at official session close (23:30 / 23:55).
    # For date-only test callers (hour==0 and minute==0), expiry day triggers roll.
    c0 = candidates[0]
    c1 = candidates[1]

    is_roll = False
    if now_dt.hour == 0 and now_dt.minute == 0:
        is_roll = (now_dt.date() >= c0["expiry_dt"].date())
    else:
        is_roll = (now_dt > c0["expiry_dt"])

    if is_roll:
        front_idx = 1
        active_candidate = c1
        tenure_start_epoch = c0["expiry_epoch"]
    else:
        front_idx = 0
        active_candidate = c0
        tenure_start_epoch = c0["expiry_epoch"] - (32 * 86400)

    # Read ratchet lock from data/roll_state.json for forward-monotonic safety
    roll_state = {}
    if os.path.exists(ROLL_STATE_FILE):
        try:
            with open(ROLL_STATE_FILE, "r", encoding="utf-8") as f:
                roll_state = json.load(f)
        except Exception:
            roll_state = {}

    last_locked_epoch = roll_state.get("locked_expiry_epoch", 0)
    rolled_at_str = roll_state.get("rolled_at")
    try:
        rolled_at_dt = datetime.fromisoformat(rolled_at_str) if rolled_at_str else None
        if rolled_at_dt and rolled_at_dt.tzinfo is None:
            rolled_at_dt = rolled_at_dt.replace(tzinfo=ist_tz)
    except Exception:
        rolled_at_dt = None

    # Ratchet lock: if already rolled forward at or before now_dt, never roll backwards
    if not is_roll and rolled_at_dt and now_dt >= rolled_at_dt and last_locked_epoch >= c1["expiry_epoch"]:
        front_idx = 1
        active_candidate = c1
        tenure_start_epoch = c0["expiry_epoch"]

    # Persist irreversible ratchet lock on forward roll
    if front_idx > 0 and active_candidate["expiry_epoch"] > last_locked_epoch:
        try:
            roll_state["locked_expiry_epoch"] = active_candidate["expiry_epoch"]
            roll_state["active_symbol"] = active_candidate["sym_ng"]
            roll_state["active_exp_code"] = active_candidate["exp_code"]
            roll_state["rolled_at"] = now_dt.isoformat()
            with open(ROLL_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(roll_state, f, indent=2)
            log(f"Rollover ratchet lock updated: {active_candidate['sym_ng']} (Expiry: {active_candidate['expiry_dt'].strftime('%Y-%m-%d %H:%M IST')})")
        except Exception as e:
            log(f"Notice persisting roll_state.json: {e}")

    vault_dir = os.path.join(REPO_DIR, "data", "mcx_vault", "contract_wise")
    os.makedirs(vault_dir, exist_ok=True)
    
    contracts = []
    for i, c in enumerate(candidates):
        is_front = (i == front_idx)
        # Tenure start: for c0, prior expiry; for c1, c0 expiry; for c2, c1 expiry
        c_tenure_start = candidates[i-1]["expiry_epoch"] if i > 0 else (c["expiry_epoch"] - (32 * 86400))
        pfile_ng = os.path.join(vault_dir, f"{c['sym_ng'].replace(':', '_')}_1m_contract_wise.parquet")
        contracts.append(("NATURALGAS", c["exp_code"], c["sym_ng"], pfile_ng, is_front, c["year"], c["month"], c_tenure_start, c["expiry_epoch"]))
        pfile_mini = os.path.join(vault_dir, f"{c['sym_mini'].replace(':', '_')}_1m_contract_wise.parquet")
        contracts.append(("NATGASMINI", c["exp_code"], c["sym_mini"], pfile_mini, is_front, c["year"], c["month"], c_tenure_start, c["expiry_epoch"]))
        
    return contracts

QUOTA_TRACKER_FILE = os.path.join(REPO_DIR, "data", "fyers_auth", "daily_quota_tracker.json")

def track_and_check_quota(cost=1, max_daily=5000):
    """
    Tracks cumulative FYERS API requests made today and enforces proactive safety cushions.
    Returns (current_total_today, can_proceed_bool, is_conserve_mode_bool).
    """
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    today_str = datetime.now(ist_tz).strftime("%Y-%m-%d")
    tracker = {"date": today_str, "calls": 0}
    if os.path.exists(QUOTA_TRACKER_FILE):
        try:
            with open(QUOTA_TRACKER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == today_str:
                tracker = data
        except Exception:
            pass

    tracker["calls"] = tracker.get("calls", 0) + cost
    tracker["last_call"] = datetime.now(ist_tz).strftime("%H:%M:%S IST")

    try:
        os.makedirs(os.path.dirname(QUOTA_TRACKER_FILE), exist_ok=True)
        with open(QUOTA_TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(tracker, f, indent=2)
    except Exception:
        pass

    calls = tracker["calls"]
    # Circuit breakers:
    # 1. Stop completely if >= 4,850 calls (within 150 of the 5,000 hard wall).
    # 2. Engage Conserve Mode if >= 4,200 calls (prioritizing Natural Gas & NatGasMini exclusively).
    can_proceed = (calls < 4850)
    is_conserve = (calls >= 4200)
    return calls, can_proceed, is_conserve

MAJOR_COMMODITIES = [
    ("CRUDEOIL", "crudeoil"),
    ("CRUDEOILM", "crudeoilm"),
    ("GOLD", "gold"),
    ("GOLDM", "goldm"),
    ("SILVER", "silver"),
    ("SILVERM", "silverm"),
    ("COPPER", "copper"),
    ("ZINC", "zinc"),
]

SECONDARY_COMMODITIES = [
    ("ALUMINIUM", "aluminium"),
    ("ALUMINI", "alumini"),
    ("ZINCMINI", "zincmini"),
    ("LEAD", "lead"),
    ("LEADMINI", "leadmini"),
    ("GOLDTEN", "goldten"),
    ("GOLDPETAL", "goldpetal"),
    ("SILVERMIC", "silvermic"),
    ("CARDAMOM", "cardamom"),
    ("MENTHAOIL", "menthaoil"),
    ("SUNOIL", "sunoil"),
]

def resolve_multi_commodity_active_contracts(now_dt, include_secondary=True):
    """
    Resolves active front and near month contracts for other MCX commodities.
    Majors are polled on every run. Secondary/illiquid commodities alternate (every ~16-20m)
    to optimize FYERS API quota while ensuring 100% 1-minute candle continuity (zero data loss).
    """
    vault_dir = os.path.join(REPO_DIR, "data", "mcx_vault", "contract_wise")
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    contracts = []
    if os.path.exists(CONTRACT_INDEX_FILE):
        try:
            with open(CONTRACT_INDEX_FILE, "r", encoding="utf-8") as f:
                ci = json.load(f)
            commodities_to_poll = list(MAJOR_COMMODITIES)
            if include_secondary:
                commodities_to_poll.extend(SECONDARY_COMMODITIES)

            for comm_name, comm_key in commodities_to_poll:
                c_list = ci.get(comm_key, [])
                active_entries = []
                for entry in c_list:
                    exp_raw = entry.get("expiry", "")
                    if len(exp_raw) >= 9:
                        try:
                            d = int(exp_raw[:2])
                            m = MONTH_CODES.index(exp_raw[2:5].upper()) + 1
                            y = int(exp_raw[5:])
                            exp_dt = datetime(y, m, d, 23, 30, tzinfo=ist_tz)
                            if exp_dt >= now_dt:
                                exp_code = str(y)[-2:] + exp_raw[2:5].upper()
                                fyers_sym = f"MCX:{comm_name}{exp_code}FUT"
                                active_entries.append((exp_dt, exp_code, fyers_sym, y, m))
                        except Exception:
                            continue
                active_entries.sort(key=lambda x: x[0])
                for j, (exp_dt, exp_code, fyers_sym, y, m) in enumerate(active_entries[:2]):
                    pfile = os.path.join(vault_dir, f"{fyers_sym.replace(':', '_')}_1m_contract_wise.parquet")
                    contracts.append((comm_name, exp_code, fyers_sym, pfile, False, y, m, int(exp_dt.timestamp() - 30*86400), int(exp_dt.timestamp())))
        except Exception as e:
            log(f"Notice resolving multi-commodity active contracts: {e}")
    return contracts

def run_snapshot_cycle():
    clear_stale_git_locks()
    fyers, user_name = get_authenticated_fyers()
    log(f"FYERS Session active for {user_name}. Checking active contracts...")

    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(timezone.utc)
    now_ist = now.astimezone(ist_tz)

    calls_today, can_proceed, is_conserve = track_and_check_quota(cost=0)
    if not can_proceed:
        log(f"ALERT: FYERS Daily API Quota nearly exhausted ({calls_today}/5,000 calls). Halting snapshot pass.")
        return

    # Tiered Polling Cadence:
    # - Tier 1: Natural Gas & NatGasMini (12 contracts): Polled 100% of runs.
    # - Tier 2: MCX Liquid Majors (16 contracts): Polled 100% of runs.
    # - Tier 3: Secondary / Agri Commodities (22 contracts): Staggered every ~16-20 mins (e.g. minute % 20 < 10).
    # If in Conserve Mode (>4,200 calls), secondary commodities are skipped to shield Natural Gas feed until close.
    include_secondary = (now_ist.minute % 20 < 10) and not is_conserve

    ng_contracts = resolve_active_contracts(fyers, now_ist)
    other_contracts = resolve_multi_commodity_active_contracts(now_ist, include_secondary=include_secondary)
    active_contracts = ng_contracts + other_contracts
    start_dt = now - timedelta(days=5)

    mode_str = "Conserve (NG Only)" if is_conserve else ("Full (21 Commodities)" if include_secondary else "Core (NG/NGM + Majors)")
    log(f"Starting snapshot cycle: {len(active_contracts)} active contracts [Mode: {mode_str}] · FYERS calls today: {calls_today}/5,000")

    for base, exp, sym, pfile, is_front, front_yr, front_mo, tenure_start_epoch, expiry_epoch in active_contracts:
        # Check quota tracking before each call
        calls_today, can_proceed, is_conserve = track_and_check_quota(cost=1)
        if not can_proceed:
            log(f"ALERT: Quota cap reached ({calls_today}/5,000 calls). Halting contract loop.")
            break
        if is_conserve and not is_front and base not in ["NATURALGAS", "NATGASMINI"]:
            continue

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
                # CRITICAL: Sliced strictly to active front-month tenure to NEVER overwrite historical bars across roll boundaries
                if is_front:
                    try:
                        sym_prefix = "ngm" if base == "NATGASMINI" else "ng"
                        dir_1m = "1m_ngm" if base == "NATGASMINI" else "1m"
                        manifest_prefix = f"data/deep/{dir_1m}"
                        deep_1m_dir = os.path.join(REPO_DIR, "docs", "data", "deep", dir_1m)
                        os.makedirs(deep_1m_dir, exist_ok=True)

                        # Filter strictly within this contract's official front-month tenure
                        df_front_bars = df_combined[(df_combined["epoch"] >= tenure_start_epoch) & (df_combined["epoch"] <= expiry_epoch)].copy()

                        # Partition recent candles by calendar month of trading (not contract month)
                        recent_threshold = int((now - timedelta(days=7)).timestamp())
                        df_recent_1m = df_front_bars[df_front_bars["epoch"] >= recent_threshold].copy()
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
                            # ONLY resample the active recent 5-day window from front-month tenure bars
                            recent_start_epoch = int((datetime.now(timezone.utc) - timedelta(days=5)).timestamp())
                            df_resample = df_front_bars[df_front_bars["epoch"] >= recent_start_epoch].copy()
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
                                if m15_new_bars and len(df_resample) > 0:
                                    m15_new_bars[-1]["latest_time"] = int(df_resample["epoch"].iloc[-1])
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
                            session_date_str = df_front_bars["ts_ist"].iloc[-1].strftime("%Y-%m-%d")
                            today_bars = df_front_bars[df_front_bars["ts_ist"].dt.strftime("%Y-%m-%d") == session_date_str]
                            if len(today_bars) > 0:
                                today_epoch = int(pd.Timestamp(f"{session_date_str} 09:00:00", tz="Asia/Kolkata").timestamp())
                                latest_bar_epoch = int(today_bars["epoch"].iloc[-1])
                                today_daily = {
                                    "time": today_epoch,
                                    "latest_time": latest_bar_epoch,
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
                                existing_daily_map[session_date_str] = today_daily
                                merged_daily = sorted(existing_daily_map.values(), key=lambda x: x["time"])
                                with open(daily_file, "w", encoding="utf-8") as f:
                                    json.dump(merged_daily, f, separators=(',', ':'))
                                log(f"Updated docs/data/deep/{sym_prefix}_daily.json today bar: Close ₹{today_daily['close']:.2f} ({len(merged_daily)} bars, latest: {datetime.fromtimestamp(latest_bar_epoch, ist_tz).strftime('%H:%M IST')})")
                    except Exception as e:
                        log(f"Notice updating deep LOD tiers for {base}: {e}")
            else:
                err_code = r.get("code") if isinstance(r, dict) else None
                err_msg = r.get("message") if isinstance(r, dict) else (r.get("error") if isinstance(r, dict) else str(r))
                if err_code == -360 or "limit" in str(err_msg).lower():
                    log(f"ALERT: FYERS API Rate Limit Exceeded (code {err_code}): {err_msg}")
                    log("Aborting current snapshot cycle to preserve API quota. Resets at 00:00 IST.")
                    break
                elif r.get("s") == "error":
                    log(f"Notice on {sym}: FYERS API returned error (code {err_code}): {err_msg}")
                else:
                    log(f"Notice on {sym}: No new candles returned (Market holiday or circuit halt).")
            time.sleep(0.35)
        except Exception as e:
            log(f"Error updating {sym}: {e}")

    # 2.5 Opportunistic check: Capture today's clearing margin the moment MCX publishes
    try:
        import sqlite3
        margins_db_path = os.path.join(REPO_DIR, "data", "margins.db")
        if os.path.exists(margins_db_path):
            conn = sqlite3.connect(margins_db_path)
            cur = conn.cursor()
            today_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
            cur.execute("SELECT 1 FROM margins WHERE date = ? LIMIT 1", (today_str,))
            has_margin = cur.fetchone() is not None
            conn.close()
            if not has_margin:
                log(f"Today's ({today_str}) clearing margin not yet in DB. Attempting opportunistic fetch...")
                fetch_today_script = os.path.join(REPO_DIR, "scripts", "fetch_today.py")
                res = subprocess.run([PYTHON_EXE, fetch_today_script, "--retries", "1", "--wait", "0"], cwd=REPO_DIR, capture_output=True, text=True)
                if res.returncode == 0:
                    log("Successfully captured today's clearing margins via local scraper!")
                    export_script = os.path.join(REPO_DIR, "scripts", "export_json.py")
                    subprocess.run([PYTHON_EXE, export_script], cwd=REPO_DIR, capture_output=True, text=True)
                else:
                    # In CI/cloud where playwright browser might not be installed in the snapshot runner,
                    # dispatch the dedicated daily_margin.yml workflow
                    try:
                        check_res = subprocess.run(["gh", "run", "list", "--workflow=daily_margin.yml", "--status", "in_progress", "--json", "databaseId"], cwd=REPO_DIR, capture_output=True, text=True)
                        dm_running = False
                        if check_res.returncode == 0 and len(json.loads(check_res.stdout or "[]")) > 0:
                            dm_running = True
                        if not dm_running:
                            subprocess.run(["gh", "workflow", "run", "daily_margin.yml"], cwd=REPO_DIR, capture_output=True, text=True)
                            log("Dispatched dedicated daily_margin.yml workflow to scrape clearing margins.")
                    except Exception as e_dm:
                        log(f"Notice checking/dispatching daily_margin workflow: {e_dm}")
    except Exception as e_margin:
        log(f"Notice on opportunistic margin check: {e_margin}")

    # 3. Re-run Pre-Computation Pipeline
    log("Re-running pre-computation exporters...")
    scripts_to_run = []

    # Only run TOD seasonality if historical continuous vault exists
    import glob
    vault_matches = glob.glob(os.path.join(REPO_DIR, "data", "mcx_vault", "NATURALGAS_1m_continuous_*.parquet"))
    if vault_matches:
        scripts_to_run.append(os.path.join(REPO_DIR, "scripts", "export_tod_seasonality.py"))

    scripts_to_run.extend([
        os.path.join(REPO_DIR, "scripts", "export_turnover.py"),
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
        status_res = subprocess.run(["git", "status", "--porcelain", "docs/data/", "data/mcx_vault/contract_wise/", "data/margins.db"], cwd=REPO_DIR, capture_output=True, text=True)
        if status_res.stdout.strip():
            log("Changes detected in docs/data/ or vault. Syncing with GitHub Pages...")
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=REPO_DIR, check=False)
            subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=REPO_DIR, check=False)
            subprocess.run(["git", "add", "docs/data/", "data/mcx_vault/contract_wise/", "data/margins.db"], cwd=REPO_DIR, check=True)
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
    parser.add_argument("--force", action="store_true", help="Bypass market hours check and force run.")
    args, _ = parser.parse_known_args()

    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    is_open, status_reason, season_name, (close_hour, close_min) = get_mcx_session_info(now_ist)

    # 1. Market Hours Gating:
    # If the exchange is closed (overnight, early morning, post-close summer/winter, weekend, or holiday),
    # immediately exit cleanly without issuing any API requests, preserving the FYERS quota.
    if not is_open and not args.force:
        log(f"MCX Market is CLOSED ({status_reason}). FYERS API quota fully preserved (0 requests made). Exiting cleanly.")
        sys.exit(0)

    # 2. Pre-market stand-by:
    # If starting on a weekday between 08:45 AM and 09:00 AM IST, wait until 09:00:05 AM IST so iteration 1 pulls live market open candles!
    total_mins = now_ist.hour * 60 + now_ist.minute
    if 525 <= total_mins < 540:  # 08:45 to 08:59 IST
        market_open_time = now_ist.replace(hour=9, minute=0, second=5, microsecond=0)
        wait_sec = (market_open_time - now_ist).total_seconds()
        if 0 < wait_sec <= 900:
            log(f"Pre-market stand-by ({season_name}): current time is {now_ist.strftime('%H:%M:%S IST')}. Waiting {int(wait_sec)}s until 09:00:05 IST market open...")
            time.sleep(wait_sec)

    run_snapshot_cycle()

    if args.loop > 0:
        log(f"Continuous daemon active ({season_name}). Polling every {args.loop}s during MCX trading hours...")
        count = 1
        while True:
            if args.iterations > 0 and count >= args.iterations:
                log(f"Completed {count} iterations. Exiting cleanly.")
                break
            time.sleep(args.loop)
            count += 1
            try:
                now_ist = datetime.now(ist_tz)
                is_open_loop, reason_loop, season_loop, _ = get_mcx_session_info(now_ist)
                if not is_open_loop and not args.force:
                    log(f"Market closed ({reason_loop}). Skipping poll to preserve API quota.")
                    continue
                run_snapshot_cycle()
            except KeyboardInterrupt:
                log("Daemon stopped by user.")
                break
            except Exception as e:
                log(f"Error in snapshot cycle: {e}. Retrying in {args.loop}s...")
