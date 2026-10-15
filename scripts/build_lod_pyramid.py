"""
build_lod_pyramid.py
--------------------
Builds and maintains the Multi-Resolution Level-of-Detail (LOD) dataset pyramid.

Modes:
1. Full Rebuild Mode (Local with Vault):
   When data/mcx_vault/NATURALGAS_1m_continuous_2019_2026.parquet exists,
   resamples and exports:
   - Tier 0: docs/data/deep/ng_daily.json   (Full 8-year daily macro bars: ~1,940 bars)
   - Tier 1: docs/data/deep/ng_1h.json      (Full 8-year 1-hour swing bars: ~28,200 bars)
   - Tier 2: docs/data/deep/ng_15m.json     (Trailing 2-year 15-minute bars: ~26,300 bars)
   - Tier 3: docs/data/deep/1m/<YYYY_MM>.json (Monthly 1-minute microstructure chunks)

2. Cloud CI Incremental Mode (GitHub Actions):
   When run without the 100MB vault parquet, it connects to data/prices.db
   (which is updated daily by fetch_prices.py) and appends new daily settlement
   bars to docs/data/deep/ng_daily.json. This keeps the deep chart updated
   100% automatically on GitHub Actions without manual backfills.
"""

import json
import os
import sys
import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np

VAULT_PARQUET = Path("data/mcx_vault/NATURALGAS_1m_continuous_2019_2026.parquet")
PRICE_DB = Path("data/prices.db")
OUTPUT_DIR = Path("docs/data/deep")
OUTPUT_1M_DIR = OUTPUT_DIR / "1m"
DAILY_JSON = OUTPUT_DIR / "ng_daily.json"

def update_daily_incremental():
    """Updates docs/data/deep/ng_daily.json using data/prices.db in CI."""
    if not PRICE_DB.exists():
        print(f"Warning: Neither vault parquet nor {PRICE_DB} exists. Skipping.")
        return

    print("Running in CI Incremental Mode: Updating ng_daily.json from prices.db...")
    if not DAILY_JSON.exists():
        print(f"Error: {DAILY_JSON} does not exist to update incrementally.")
        return

    with open(DAILY_JSON, "r") as f:
        daily_bars = json.load(f)

    latest_epoch = daily_bars[-1]["time"] if daily_bars else 0
    latest_dt = pd.to_datetime(latest_epoch, unit="s", utc=True).tz_convert("Asia/Kolkata")
    latest_date_str = latest_dt.strftime("%Y-%m-%d")
    print(f"Latest bar in ng_daily.json: {latest_date_str} (epoch {latest_epoch})")

    # Connect to prices.db and get front-month prices for subsequent dates
    conn = sqlite3.connect(PRICE_DB)
    query = """
        SELECT date, open, high, low, close, volume_lots as volume
        FROM prices
        WHERE symbol = 'NATURALGAS' AND instrument = 'FUTCOM' AND date >= ?
        ORDER BY date ASC, volume_lots DESC
    """
    df = pd.read_sql_query(query, conn, params=(latest_date_str,))
    conn.close()

    if df.empty:
        print("No newer price data found in prices.db.")
        return

    # Keep highest-volume contract for each date (front-month)
    df = df.drop_duplicates(subset=["date"], keep="first")

    # Filter strictly newer dates
    added = 0
    existing_epochs = {b["time"] for b in daily_bars}
    for _, row in df.iterrows():
        # Set timestamp to 09:00:00 IST for consistent trading session epoch
        ts = pd.Timestamp(f"{row['date']} 09:00:00", tz="Asia/Kolkata")
        epoch_sec = int(ts.timestamp())
        if epoch_sec not in existing_epochs and row["close"] > 0:
            daily_bars.append({
                "time": epoch_sec,
                "open": round(float(row["open"] if row["open"] > 0 else row["close"]), 2),
                "high": round(float(row["high"] if row["high"] > 0 else row["close"]), 2),
                "low": round(float(row["low"] if row["low"] > 0 else row["close"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"])
            })
            existing_epochs.add(epoch_sec)
            added += 1

    if added > 0:
        daily_bars.sort(key=lambda x: x["time"])
        with open(DAILY_JSON, "w") as f:
            json.dump(daily_bars, f, separators=(',', ':'))
        print(f"Successfully added {added} new trading day(s) to {DAILY_JSON}. Total bars: {len(daily_bars)}")
    else:
        print("ng_daily.json is already completely up to date.")

def full_vault_rebuild():
    """Builds full 3-tier LOD pyramid from 1.65M 1-minute continuous vault."""
    print(f"Loading 1m vault: {VAULT_PARQUET}...")
    df = pd.read_parquet(VAULT_PARQUET)
    print(f"Loaded {len(df):,} raw bars.")

    df["dt"] = pd.to_datetime(df["epoch"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    df = df.set_index("dt").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_1M_DIR.mkdir(parents=True, exist_ok=True)

    # ── Tier 0: Daily ──
    print("Resampling Daily tier (2019-2026)...")
    daily = df.resample("1D").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "epoch": "first"
    }).dropna(subset=["close"])

    daily_bars = []
    for dt, row in daily.iterrows():
        daily_bars.append({
            "time": int(row["epoch"]),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"])
        })
    with open(DAILY_JSON, "w") as f:
        json.dump(daily_bars, f, separators=(',', ':'))
    print(f"Wrote Tier 0 Daily: {len(daily_bars):,} bars -> {DAILY_JSON} ({DAILY_JSON.stat().st_size / 1024:.1f} KB)")

    # ── Tier 1: 1-Hour ──
    print("Resampling 1-Hour tier (2019-2026)...")
    h1 = df.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "epoch": "first"
    }).dropna(subset=["close"])

    h1_bars = []
    for dt, row in h1.iterrows():
        h1_bars.append({
            "time": int(row["epoch"]),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"])
        })
    h1_file = OUTPUT_DIR / "ng_1h.json"
    with open(h1_file, "w") as f:
        json.dump(h1_bars, f, separators=(',', ':'))
    print(f"Wrote Tier 1 1-Hour: {len(h1_bars):,} bars -> {h1_file} ({h1_file.stat().st_size / 1024:.1f} KB)")

    # ── Tier 2: 15-Minute ──
    print("Resampling 15-Minute tier (2025-2026)...")
    df_recent = df[df.index >= "2025-01-01"]
    m15 = df_recent.resample("15min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "epoch": "first"
    }).dropna(subset=["close"])

    m15_bars = []
    for dt, row in m15.iterrows():
        m15_bars.append({
            "time": int(row["epoch"]),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"])
        })
    m15_file = OUTPUT_DIR / "ng_15m.json"
    with open(m15_file, "w") as f:
        json.dump(m15_bars, f, separators=(',', ':'))
    print(f"Wrote Tier 2 15-Minute: {len(m15_bars):,} bars -> {m15_file} ({m15_file.stat().st_size / 1024:.1f} KB)")

    # ── Tier 3: 1-Minute Monthly Chunks ──
    print("Generating Tier 3 Monthly 1-Minute chunks for trailing 12 months...")
    df_1m = df[df.index >= "2025-10-01"].copy()
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
        target_file = OUTPUT_1M_DIR / f"{ym}.json"
        with open(target_file, "w") as f:
            json.dump(month_bars, f, separators=(',', ':'))
        print(f"  Month {ym}: {len(month_bars):,} 1m bars -> {target_file.name} ({target_file.stat().st_size / 1024:.1f} KB)")
        manifest_1m.append({
            "month": ym,
            "bars": len(month_bars),
            "start": int(group["epoch"].iloc[0]),
            "end": int(group["epoch"].iloc[-1]),
            "file": f"data/deep/1m/{ym}.json"
        })

    manifest_file = OUTPUT_DIR / "manifest.json"
    manifest_data = {
        "daily": {"file": "data/deep/ng_daily.json", "bars": len(daily_bars)},
        "h1": {"file": "data/deep/ng_1h.json", "bars": len(h1_bars)},
        "m15": {"file": "data/deep/ng_15m.json", "bars": len(m15_bars)},
        "m1_months": manifest_1m
    }
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f, indent=2)
    print("LOD data pyramid successfully built.")

def main():
    if VAULT_PARQUET.exists() and "--incremental" not in sys.argv:
        full_vault_rebuild()
    else:
        update_daily_incremental()

if __name__ == "__main__":
    main()
