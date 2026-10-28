"""
build_lod_pyramid.py
--------------------
Builds and maintains the Multi-Resolution Level-of-Detail (LOD) dataset pyramid.

Modes:
1. Full Rebuild Mode (Local with Vault):
   When data/mcx_vault/NATURALGAS_1m_continuous_2019_2026.parquet exists,
   merges contracts strictly at official expiry boundaries and exports:
   - Tier 0: docs/data/deep/ng_daily.json   (Full 8-year daily macro bars: ~1,940 bars)
   - Tier 1: docs/data/deep/ng_1h.json      (Full 8-year 1-hour swing bars: ~28,200 bars)
   - Tier 2: docs/data/deep/ng_15m.json     (Trailing 2-year 15-minute bars: ~26,300 bars)
   - Tier 3: docs/data/deep/1m/<YYYY_MM>.json (Monthly 1-minute microstructure chunks)
   - Manifest: docs/data/deep/manifest.json
   - Rollovers: docs/data/deep/rollovers.json

2. Cloud CI Incremental Mode (GitHub Actions):
   When run without the 100MB vault parquet, it connects to data/prices.db
   (which is updated daily by fetch_prices.py) and appends new daily settlement
   bars to docs/data/deep/ng_daily.json. This keeps the deep chart updated
   100% automatically on GitHub Actions without manual backfills.
"""

import json
import os
import sys
import re
import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np

VAULT_DIR = Path("data/mcx_vault")
PRICE_DB = Path("data/prices.db")
OUTPUT_DIR = Path("docs/data/deep")

# Official MCX Natural Gas Expiration Schedule
MCX_NG_EXPIRY_SCHEDULE = {
    # 2026
    "26JAN": "2026-01-27 23:55:00",
    "26FEB": "2026-02-24 23:55:00",
    "26MAR": "2026-03-26 23:30:00",
    "26APR": "2026-04-27 23:30:00",
    "26MAY": "2026-05-26 23:30:00",
    "26JUN": "2026-06-25 23:30:00",
    "26JUL": "2026-07-28 23:30:00",
    "26AUG": "2026-08-26 23:30:00",
    "26SEP": "2026-09-25 23:30:00",
    "26OCT": "2026-10-27 23:30:00",
    "26NOV": "2026-11-24 23:55:00",
    "26DEC": "2026-12-28 23:55:00",
    # 2027
    "27JAN": "2027-01-25 23:55:00",
    "27FEB": "2027-02-23 23:55:00",
    "27MAR": "2027-03-25 23:30:00",
    "27APR": "2027-04-27 23:30:00",
    "27MAY": "2027-05-26 23:30:00",
    "27JUN": "2027-06-25 23:30:00",
    "27JUL": "2027-07-27 23:30:00",
    "27AUG": "2027-08-26 23:30:00",
    "27SEP": "2027-09-27 23:30:00",
    "27OCT": "2027-10-26 23:30:00",
    "27NOV": "2027-11-24 23:55:00",
    "27DEC": "2027-12-28 23:55:00",
}

def find_vault_parquet(name: str) -> Path:
    """Dynamically locates the continuous 1-minute vault parquet, adapting to any year range."""
    candidates = sorted(VAULT_DIR.glob(f"{name}_1m_continuous_*.parquet"))
    if candidates:
        return candidates[-1]
    return VAULT_DIR / f"{name}_1m_continuous_2019_2026.parquet"

_MONTH_ORDER = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

def _contract_file_sort_key(p: Path):
    """Sorts contract parquets by chronological expiry (e.g. 26OCT before 26NOV before 26DEC before 27JAN)."""
    m = re.search(r"(\d{2})([A-Z]{3})FUT", p.name)
    if not m:
        return (9999, 99)
    yy, mmm = m.groups()
    yr = int(yy) + 2000
    mon = _MONTH_ORDER.index(mmm) + 1 if mmm in _MONTH_ORDER else 99
    return (yr, mon)

def get_contract_expiry_epoch(exp_code: str, fallback_last_epoch: int) -> int:
    """Returns official contract expiry epoch (Asia/Kolkata)."""
    if exp_code in MCX_NG_EXPIRY_SCHEDULE:
        ts = pd.Timestamp(MCX_NG_EXPIRY_SCHEDULE[exp_code], tz="Asia/Kolkata")
        return int(ts.timestamp())
    # Dynamic fallback: query docs/data/contract_index.json or standard 26th
    try:
        ci_path = Path("docs/data/contract_index.json")
        if ci_path.exists():
            import json
            with open(ci_path, "r", encoding="utf-8") as f:
                ci = json.load(f)
            for item in ci.get("ng", []):
                exp_raw = item.get("expiry", "")
                if exp_code in exp_raw:
                    from datetime import datetime
                    dt_p = datetime.strptime(exp_raw, "%d%b%Y")
                    close_str = "23:55:00" if dt_p.month in [11, 12, 1, 2] else "23:30:00"
                    ts = pd.Timestamp(f"{dt_p.strftime('%Y-%m-%d')} {close_str}", tz="Asia/Kolkata")
                    return int(ts.timestamp())
    except Exception:
        pass
    return fallback_last_epoch

def find_contract_wise_parquets(name: str) -> list[Path]:
    """Dynamically discovers all contract-wise 1m parquets for the commodity sorted chronologically by expiry."""
    contract_dir = VAULT_DIR / "contract_wise"
    if not contract_dir.exists():
        return []
    files = list(contract_dir.glob(f"MCX_{name}*FUT_1m_contract_wise.parquet"))
    return sorted(files, key=_contract_file_sort_key)

SYMBOLS_CONFIG = [
    {
        "name": "NATURALGAS",
        "prefix": "ng",
        "vault_parquet": find_vault_parquet("NATURALGAS"),
        "dir_1m": OUTPUT_DIR / "1m",
        "manifest_1m_prefix": "data/deep/1m"
    },
    {
        "name": "NATGASMINI",
        "prefix": "ngm",
        "vault_parquet": find_vault_parquet("NATGASMINI"),
        "dir_1m": OUTPUT_DIR / "1m_ngm",
        "manifest_1m_prefix": "data/deep/1m_ngm"
    }
]

def update_daily_incremental_for_sym(sym_cfg):
    """Updates docs/data/deep/{prefix}_daily.json using data/prices.db in CI."""
    if not PRICE_DB.exists():
        print(f"Warning: Neither vault parquet nor {PRICE_DB} exists for {sym_cfg['name']}. Skipping.")
        return

    daily_json = OUTPUT_DIR / f"{sym_cfg['prefix']}_daily.json"
    if not daily_json.exists():
        print(f"Warning: {daily_json} does not exist to update incrementally.")
        return

    print(f"Running in CI Incremental Mode: Updating {daily_json.name} from prices.db...")
    with open(daily_json, "r") as f:
        daily_bars = json.load(f)

    latest_epoch = daily_bars[-1]["time"] if daily_bars else 0
    latest_dt = pd.to_datetime(latest_epoch, unit="s", utc=True).tz_convert("Asia/Kolkata")
    latest_date_str = latest_dt.strftime("%Y-%m-%d")
    print(f"Latest bar in {daily_json.name}: {latest_date_str} (epoch {latest_epoch})")

    conn = sqlite3.connect(PRICE_DB)
    query = """
        SELECT date, open, high, low, close, volume_lots as volume
        FROM prices
        WHERE symbol = ? AND instrument = 'FUTCOM' AND date >= ?
        ORDER BY date ASC, volume_lots DESC
    """
    df = pd.read_sql_query(query, conn, params=(sym_cfg["name"], latest_date_str))
    conn.close()

    if df.empty:
        print(f"No newer price data found for {sym_cfg['name']} in prices.db.")
        return

    df = df.drop_duplicates(subset=["date"], keep="first")
    added = 0
    existing_epochs = {b["time"] for b in daily_bars}
    existing_dates = {
        pd.to_datetime(b["time"], unit="s", utc=True).tz_convert("Asia/Kolkata").strftime("%Y-%m-%d")
        for b in daily_bars
    }
    for _, row in df.iterrows():
        row_date = str(row["date"])
        ts = pd.Timestamp(f"{row_date} 09:00:00", tz="Asia/Kolkata")
        epoch_sec = int(ts.timestamp())
        if epoch_sec not in existing_epochs and row_date not in existing_dates and row["close"] > 0:
            daily_bars.append({
                "time": epoch_sec,
                "open": round(float(row["open"] if row["open"] > 0 else row["close"]), 2),
                "high": round(float(row["high"] if row["high"] > 0 else row["close"]), 2),
                "low": round(float(row["low"] if row["low"] > 0 else row["close"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"])
            })
            existing_epochs.add(epoch_sec)
            existing_dates.add(row_date)
            added += 1

    if added > 0:
        daily_bars.sort(key=lambda x: x["time"])
        with open(daily_json, "w") as f:
            json.dump(daily_bars, f, separators=(',', ':'))
        print(f"Successfully added {added} new trading day(s) to {daily_json}. Total bars: {len(daily_bars)}")
    else:
        print(f"{daily_json.name} is already completely up to date.")

def build_symbol_pyramid(sym_cfg):
    """Builds full 3-tier LOD pyramid for a specific symbol configuration with clean rollover stitching."""
    vault_parquet = sym_cfg["vault_parquet"]
    if not vault_parquet.exists():
        print(f"Vault parquet not found for {sym_cfg['name']} ({vault_parquet}). Skipping.")
        return None

    print(f"\n[{sym_cfg['name']}] Loading vault: {vault_parquet}...")
    df = pd.read_parquet(vault_parquet)
    print(f"[{sym_cfg['name']}] Loaded {len(df):,} raw bars from vault (Max Epoch: {df['epoch'].max()}).")

    # Discover and sort contract parquets chronologically
    contract_files = find_contract_wise_parquets(sym_cfg["name"])
    rollovers = []

    if contract_files:
        print(f"[{sym_cfg['name']}] Assembling {len(contract_files)} contracts strictly at chronological expiry boundaries...")
        contracts_meta = []
        for cp in contract_files:
            try:
                m = re.search(r"(\d{2}[A-Z]{3})FUT", cp.name)
                exp_code = m.group(1) if m else "UNKNOWN"
                df_c = pd.read_parquet(cp)
                if df_c.empty:
                    continue
                last_epoch = int(df_c["epoch"].max())
                exp_epoch = get_contract_expiry_epoch(exp_code, last_epoch)
                sym_tag = cp.name.replace("_1m_contract_wise.parquet", "").replace("_", ":")
                contracts_meta.append({
                    "file": cp,
                    "code": exp_code,
                    "symbol": sym_tag,
                    "df": df_c,
                    "expiry_epoch": exp_epoch,
                    "last_epoch": last_epoch
                })
            except Exception as e:
                print(f"[{sym_cfg['name']}] Notice inspecting {cp.name}: {e}")

        # Preserve strict chronological sort by (year, month)
        contracts_meta.sort(key=lambda x: _contract_file_sort_key(x["file"]))

        merged_pieces = [df]
        current_cursor = int(df["epoch"].max())

        for idx, cm in enumerate(contracts_meta):
            c_df = cm["df"]
            c_code = cm["code"]
            c_exp = cm["expiry_epoch"]

            if c_exp <= current_cursor:
                continue

            tenure_start = current_cursor
            tenure_end = c_exp

            # Strict slice: only bars within this contract's front-month tenure
            c_slice = c_df[(c_df["epoch"] > tenure_start) & (c_df["epoch"] <= tenure_end)].copy()

            if not c_slice.empty:
                merged_pieces.append(c_slice)
                start_ist = pd.to_datetime(int(c_slice['epoch'].iloc[0]), unit='s', utc=True).tz_convert('Asia/Kolkata')
                end_ist = pd.to_datetime(int(c_slice['epoch'].iloc[-1]), unit='s', utc=True).tz_convert('Asia/Kolkata')
                print(f"  [{sym_cfg['name']}] Contract {c_code}: merged {len(c_slice):,} bars ({start_ist.strftime('%Y-%m-%d %H:%M')} -> {end_ist.strftime('%Y-%m-%d %H:%M IST')})")

                # Detect and calculate official rollover spread from previous contract
                if idx > 0 and tenure_start > 0:
                    prev_cm = contracts_meta[idx - 1]
                    prev_df = prev_cm["df"]
                    old_bars = prev_df[prev_df["epoch"] <= tenure_start]
                    new_bars = c_df[c_df["epoch"] <= tenure_start]

                    if not old_bars.empty and not new_bars.empty:
                        old_close = round(float(old_bars["close"].iloc[-1]), 2)
                        new_close = round(float(new_bars["close"].iloc[-1]), 2)
                        spread = round(new_close - old_close, 2)
                        roll_time = int(c_slice["epoch"].iloc[0])
                        roll_dt_ist = pd.to_datetime(roll_time, unit="s", utc=True).tz_convert("Asia/Kolkata")

                        rollover_entry = {
                            "time": roll_time,
                            "expiry_epoch": int(old_bars["epoch"].iloc[-1]),
                            "date": roll_dt_ist.strftime("%Y-%m-%d"),
                            "timestamp_ist": roll_dt_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
                            "from_symbol": prev_cm["symbol"],
                            "to_symbol": cm["symbol"],
                            "old_close": old_close,
                            "new_close": new_close,
                            "spread": spread
                        }
                        rollovers.append(rollover_entry)
                        print(f"  [{sym_cfg['name']}] Rollover calculated: {prev_cm['code']} -> {c_code} | Spread: {spread:+.2f} (Old: {old_close:.2f}, New: {new_close:.2f}) at {roll_dt_ist.strftime('%Y-%m-%d %H:%M IST')}")

                current_cursor = int(c_slice["epoch"].iloc[-1])

        df = pd.concat(merged_pieces, ignore_index=True)
        df = df.drop_duplicates(subset=["epoch"], keep="first").sort_values("epoch").reset_index(drop=True)
        print(f"[{sym_cfg['name']}] Clean assembly complete: {len(df):,} total bars.")

    df["dt"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    df = df.set_index("dt").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dir_1m = sym_cfg["dir_1m"]
    dir_1m.mkdir(parents=True, exist_ok=True)
    prefix = sym_cfg["prefix"]

    # ── Tier 0: Daily ──
    print(f"[{sym_cfg['name']}] Resampling Daily tier...")
    daily = df.resample("1D").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "epoch": "first"
    }).dropna(subset=["close"])

    daily_bars = []
    for dt, row in daily.iterrows():
        # Anchor daily bars to 09:00:00 IST of that trading day
        daily_time = int(pd.Timestamp(f"{dt.strftime('%Y-%m-%d')} 09:00:00", tz="Asia/Kolkata").timestamp())
        daily_bars.append({
            "time": daily_time,
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"])
        })
    if daily_bars:
        daily_bars[-1]["latest_time"] = int(df["epoch"].iloc[-1])

    daily_file = OUTPUT_DIR / f"{prefix}_daily.json"
    with open(daily_file, "w") as f:
        json.dump(daily_bars, f, separators=(',', ':'))
    print(f"[{sym_cfg['name']}] Wrote Tier 0 Daily: {len(daily_bars):,} bars -> {daily_file.name} ({daily_file.stat().st_size / 1024:.1f} KB)")

    # ── Tier 1: 1-Hour ──
    print(f"[{sym_cfg['name']}] Resampling 1-Hour tier...")
    h1 = df.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "epoch": "first"
    }).dropna(subset=["close"])

    h1_bars = []
    for dt, row in h1.iterrows():
        h1_bars.append({
            "time": int(dt.timestamp()),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"])
        })
    h1_file = OUTPUT_DIR / f"{prefix}_1h.json"
    with open(h1_file, "w") as f:
        json.dump(h1_bars, f, separators=(',', ':'))
    print(f"[{sym_cfg['name']}] Wrote Tier 1 1-Hour: {len(h1_bars):,} bars -> {h1_file.name} ({h1_file.stat().st_size / 1024:.1f} KB)")

    # ── Tier 2: 15-Minute (Trailing 24 Months) ──
    latest_dt = df.index.max()
    cutoff_24m = (latest_dt - pd.DateOffset(months=24)).strftime("%Y-%m-01")
    print(f"[{sym_cfg['name']}] Resampling 15-Minute tier (from {cutoff_24m} to {latest_dt.strftime('%Y-%m-%d')})...")
    df_recent = df[df.index >= cutoff_24m]
    m15 = df_recent.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "epoch": "first"
    }).dropna(subset=["close"])

    m15_bars = []
    for dt, row in m15.iterrows():
        m15_bars.append({
            "time": int(dt.timestamp()),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"])
        })
    if m15_bars:
        m15_bars[-1]["latest_time"] = int(df["epoch"].iloc[-1])

    m15_file = OUTPUT_DIR / f"{prefix}_15m.json"
    with open(m15_file, "w") as f:
        json.dump(m15_bars, f, separators=(',', ':'))
    print(f"[{sym_cfg['name']}] Wrote Tier 2 15-Minute: {len(m15_bars):,} bars -> {m15_file.name} ({m15_file.stat().st_size / 1024:.1f} KB)")

    # ── Tier 3: 1-Minute Monthly Chunks (Trailing 12 Months) ──
    cutoff_12m = (latest_dt - pd.DateOffset(months=12)).strftime("%Y-%m-01")
    print(f"[{sym_cfg['name']}] Generating Tier 3 Monthly 1-Minute chunks for trailing 12 months (from {cutoff_12m})...")
    df_1m = df[df.index >= cutoff_12m].copy()
    df_1m["ym"] = df_1m.index.strftime("%Y_%m")

    manifest_1m = []
    for ym, group in df_1m.groupby("ym"):
        month_bars = []
        for dt, row in group.iterrows():
            month_bars.append([
                int(row["epoch"]),
                round(float(row["open"]), 2),
                round(float(row["high"]), 2),
                round(float(row["low"]), 2),
                round(float(row["close"]), 2),
                int(row["volume"])
            ])
        target_file = dir_1m / f"{ym}.json"
        with open(target_file, "w") as f:
            json.dump(month_bars, f, separators=(',', ':'))
        print(f"  [{sym_cfg['name']}] Month {ym}: {len(month_bars):,} 1m bars -> {target_file.name} ({target_file.stat().st_size / 1024:.1f} KB)")
        manifest_1m.append({
            "month": ym,
            "bars": len(month_bars),
            "start": int(group["epoch"].iloc[0]),
            "end": int(group["epoch"].iloc[-1]),
            "file": f"{sym_cfg['manifest_1m_prefix']}/{ym}.json"
        })

    return {
        "meta": {
            "daily": {"file": f"data/deep/{prefix}_daily.json", "bars": len(daily_bars)},
            "h1": {"file": f"data/deep/{prefix}_1h.json", "bars": len(h1_bars)},
            "m15": {"file": f"data/deep/{prefix}_15m.json", "bars": len(m15_bars)},
            "m1_months": manifest_1m
        },
        "rollovers": rollovers
    }

def full_vault_rebuild():
    """Builds full LOD pyramids for both NATURALGAS and NATGASMINI and exports rollovers.json."""
    manifest_data = {}
    rollovers_data = {}
    for sym_cfg in SYMBOLS_CONFIG:
        res = build_symbol_pyramid(sym_cfg)
        if res:
            manifest_data[sym_cfg["prefix"]] = res["meta"]
            rollovers_data[sym_cfg["prefix"]] = res["rollovers"]

    manifest_file = OUTPUT_DIR / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"\nManifest successfully updated -> {manifest_file}")

    rollovers_file = OUTPUT_DIR / "rollovers.json"
    with open(rollovers_file, "w") as f:
        json.dump(rollovers_data, f, indent=2)
    print(f"Rollovers successfully updated -> {rollovers_file}")

def main():
    has_any_vault = any(cfg["vault_parquet"].exists() for cfg in SYMBOLS_CONFIG)
    if has_any_vault and "--incremental" not in sys.argv:
        full_vault_rebuild()
    else:
        for sym_cfg in SYMBOLS_CONFIG:
            update_daily_incremental_for_sym(sym_cfg)

if __name__ == "__main__":
    main()
